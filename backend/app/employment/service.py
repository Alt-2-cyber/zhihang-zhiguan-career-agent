import hashlib
import json
import secrets
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.applications.models import Application
from app.auth.models import User
from app.core.errors import AppError
from app.core.models import utc_now
from app.employment.models import (
    EmployeeFeedback,
    EmployerInvitation,
    EmployerReview,
    EmploymentRecord,
    FeedbackModeration,
    FollowupSurvey,
    InterviewExperience,
)
from app.jobs.models import Job

FOLLOWUP_DAYS = {"day_7": 7, "day_30": 30, "day_90": 90, "day_180": 180}
EMPLOYER_SCORE_KEYS = {
    "role_readiness",
    "professional_skill",
    "learning",
    "communication",
    "delivery_quality",
    "initiative",
    "professionalism",
}
EMPLOYEE_SCORE_KEYS = {
    "job_consistency",
    "interview_difficulty",
    "workload",
    "mentoring",
    "team_climate",
    "compensation_delivery",
    "growth_space",
}


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def validate_scores(scores: dict[str, int], expected: set[str]) -> None:
    if set(scores) != expected or any(
        not isinstance(value, int) or not 1 <= value <= 5 for value in scores.values()
    ):
        raise AppError(422, "feedback_scores_invalid", "评价维度不完整或评分不在 1 到 5 之间")


def ensure_followups(db: Session, employment: EmploymentRecord) -> list[FollowupSurvey]:
    existing = {
        item.milestone: item
        for item in db.scalars(
            select(FollowupSurvey).where(FollowupSurvey.employment_id == employment.id)
        ).all()
    }
    for milestone, days in FOLLOWUP_DAYS.items():
        if milestone not in existing:
            item = FollowupSurvey(
                employment_id=employment.id,
                student_id=employment.student_id,
                milestone=milestone,
                due_date=employment.onboard_date + timedelta(days=days),
                status="scheduled",
            )
            db.add(item)
            existing[milestone] = item
    return list(existing.values())


def generate_all_followups(db: Session) -> int:
    created = 0
    for employment in db.scalars(
        select(EmploymentRecord).where(EmploymentRecord.status == "employed")
    ).all():
        before = int(
            db.scalar(
                select(func.count())
                .select_from(FollowupSurvey)
                .where(FollowupSurvey.employment_id == employment.id)
            )
            or 0
        )
        ensure_followups(db, employment)
        after_expected = len(FOLLOWUP_DAYS)
        created += max(0, after_expected - before)
    db.commit()
    return created


def create_employment(
    db: Session,
    *,
    student: User,
    application_id: str,
    onboard_date: date,
    consent: bool,
    commit: bool = True,
) -> EmploymentRecord:
    application = db.get(Application, application_id)
    if application is None or application.student_id != student.id:
        raise AppError(404, "application_not_found", "投递记录不存在")
    if application.stage != "offered":
        raise AppError(409, "application_not_offered", "只有已录用的投递才能建立就业记录")
    existing = db.scalar(
        select(EmploymentRecord).where(EmploymentRecord.application_id == application.id)
    )
    if existing is not None:
        return existing
    job = db.get(Job, application.job_id)
    if job is None:
        raise AppError(409, "employment_job_missing", "录用岗位不存在")
    item = EmploymentRecord(
        student_id=student.id,
        application_id=application.id,
        company=job.company,
        job_title=job.title,
        onboard_date=onboard_date,
        student_consent=consent,
        employer_invitation_enabled=consent,
    )
    db.add(item)
    db.flush()
    ensure_followups(db, item)
    if commit:
        db.commit()
        db.refresh(item)
    else:
        db.flush()
    return item


def employment_summary(db: Session, item: EmploymentRecord) -> dict[str, object]:
    surveys = db.scalars(
        select(FollowupSurvey)
        .where(FollowupSurvey.employment_id == item.id)
        .order_by(FollowupSurvey.due_date)
    ).all()
    own_feedback = db.scalar(
        select(EmployeeFeedback).where(EmployeeFeedback.employment_id == item.id)
    )
    interview = db.scalar(
        select(InterviewExperience).where(InterviewExperience.employment_id == item.id)
    )
    employer_review_exists = (
        db.scalar(select(EmployerReview.id).where(EmployerReview.employment_id == item.id))
        is not None
    )
    return {
        "id": item.id,
        "application_id": item.application_id,
        "company": item.company,
        "job_title": item.job_title,
        "onboard_date": item.onboard_date.isoformat(),
        "status": item.status,
        "student_consent": item.student_consent,
        "employer_invitation_enabled": item.employer_invitation_enabled,
        "employer_review_received": employer_review_exists,
        "employee_feedback": None
        if own_feedback is None
        else {
            "overall_score": own_feedback.overall_score,
            "scores": json.loads(own_feedback.scores_json),
            "requirements": own_feedback.requirements,
            "experience": own_feedback.experience,
            "recommendation": own_feedback.recommendation,
            "would_recommend": own_feedback.would_recommend,
            "moderation_status": own_feedback.moderation_status,
        },
        "interview_experience": None
        if interview is None
        else {
            "difficulty": interview.difficulty,
            "rounds": interview.rounds,
            "process": interview.process,
            "questions": interview.questions,
            "advice": interview.advice,
            "moderation_status": interview.moderation_status,
        },
        "followups": [
            {
                "id": survey.id,
                "milestone": survey.milestone,
                "due_date": survey.due_date.isoformat(),
                "status": survey.status,
                "student_completed_at": survey.student_completed_at.isoformat()
                if survey.student_completed_at
                else None,
                "employer_completed_at": survey.employer_completed_at.isoformat()
                if survey.employer_completed_at
                else None,
            }
            for survey in surveys
        ],
    }


def create_employer_invitation(
    db: Session, *, student_id: str, employment_id: str, expires_days: int = 14
) -> tuple[EmployerInvitation, str]:
    employment = db.get(EmploymentRecord, employment_id)
    if employment is None or employment.student_id != student_id:
        raise AppError(404, "employment_not_found", "就业记录不存在")
    if not employment.student_consent or not employment.employer_invitation_enabled:
        raise AppError(409, "employer_invitation_not_consented", "请先授权企业参与就业质量回访")
    if db.scalar(select(EmployerReview.id).where(EmployerReview.employment_id == employment.id)):
        raise AppError(409, "employer_review_exists", "企业评价已经提交")
    now = utc_now()
    for old in db.scalars(
        select(EmployerInvitation).where(
            EmployerInvitation.employment_id == employment.id,
            EmployerInvitation.used_at.is_(None),
            EmployerInvitation.revoked_at.is_(None),
        )
    ).all():
        old.revoked_at = now
    token = secrets.token_urlsafe(32)
    invitation = EmployerInvitation(
        employment_id=employment.id,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        expires_at=now + timedelta(days=expires_days),
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)
    return invitation, token


def resolve_invitation(
    db: Session, token: str, *, for_update: bool = False
) -> tuple[EmployerInvitation, EmploymentRecord]:
    digest = hashlib.sha256(token.encode()).hexdigest()
    statement = select(EmployerInvitation).where(EmployerInvitation.token_hash == digest)
    if for_update:
        statement = statement.with_for_update()
    invitation = db.scalar(statement)
    if (
        invitation is None
        or invitation.used_at
        or invitation.revoked_at
        or _aware(invitation.expires_at) <= utc_now()
    ):
        raise AppError(404, "employer_invitation_invalid", "评价邀请无效或已过期")
    employment = db.get(EmploymentRecord, invitation.employment_id)
    if employment is None or not employment.student_consent:
        raise AppError(404, "employer_invitation_invalid", "评价邀请无效或已过期")
    return invitation, employment


def submit_employer_review(
    db: Session,
    *,
    token: str,
    scores: dict[str, int],
    trial_result: str,
    strengths: str,
    improvement: str,
    curriculum_suggestion: str | None,
) -> EmployerReview:
    validate_scores(scores, EMPLOYER_SCORE_KEYS)
    invitation, employment = resolve_invitation(db, token, for_update=True)
    if db.scalar(select(EmployerReview.id).where(EmployerReview.employment_id == employment.id)):
        raise AppError(409, "employer_review_exists", "企业评价已经提交")
    review = EmployerReview(
        employment_id=employment.id,
        scores_json=json.dumps(scores, ensure_ascii=False),
        overall_score=round(sum(scores.values()) / len(scores)),
        trial_result=trial_result,
        strengths=strengths,
        improvement=improvement,
        curriculum_suggestion=curriculum_suggestion,
        submitted_at=utc_now(),
    )
    db.add(review)
    invitation.used_at = utc_now()
    due = db.scalar(
        select(FollowupSurvey)
        .where(
            FollowupSurvey.employment_id == employment.id, FollowupSurvey.due_date <= date.today()
        )
        .order_by(FollowupSurvey.due_date.desc())
    )
    if due:
        due.employer_completed_at = utc_now()
        due.status = "partially_completed" if due.student_completed_at is None else "completed"
    db.commit()
    db.refresh(review)
    return review


def submit_employee_feedback(
    db: Session,
    *,
    student_id: str,
    employment_id: str,
    scores: dict[str, int],
    requirements: str,
    experience: str,
    recommendation: str,
    would_recommend: bool,
    interview_data: dict[str, object],
) -> EmployeeFeedback:
    validate_scores(scores, EMPLOYEE_SCORE_KEYS)
    employment = db.get(EmploymentRecord, employment_id)
    if employment is None or employment.student_id != student_id:
        raise AppError(404, "employment_not_found", "就业记录不存在")
    feedback = db.scalar(
        select(EmployeeFeedback).where(EmployeeFeedback.employment_id == employment.id)
    )
    if feedback is None:
        feedback = EmployeeFeedback(
            employment_id=employment.id, student_id=student_id, submitted_at=utc_now()
        )
        db.add(feedback)
    feedback.scores_json = json.dumps(scores, ensure_ascii=False)
    feedback.overall_score = round(sum(scores.values()) / len(scores))
    feedback.requirements = requirements
    feedback.experience = experience
    feedback.recommendation = recommendation
    feedback.would_recommend = would_recommend
    feedback.moderation_status = "pending"
    interview = db.scalar(
        select(InterviewExperience).where(InterviewExperience.employment_id == employment.id)
    )
    if interview is None:
        interview = InterviewExperience(employment_id=employment.id, student_id=student_id)
        db.add(interview)
    interview.difficulty = int(interview_data["difficulty"])
    interview.rounds = int(interview_data["rounds"])
    interview.process = str(interview_data["process"])
    interview.questions = str(interview_data["questions"])
    interview.advice = str(interview_data["advice"])
    interview.moderation_status = "pending"
    due = db.scalar(
        select(FollowupSurvey)
        .where(
            FollowupSurvey.employment_id == employment.id, FollowupSurvey.due_date <= date.today()
        )
        .order_by(FollowupSurvey.due_date.desc())
    )
    if due:
        due.student_completed_at = utc_now()
        due.status = "partially_completed" if due.employer_completed_at is None else "completed"
    db.commit()
    db.refresh(feedback)
    return feedback


def enterprise_profile(db: Session, company: str, *, min_samples: int = 3) -> dict[str, object]:
    rows = db.execute(
        select(EmployeeFeedback, EmploymentRecord, InterviewExperience)
        .join(EmploymentRecord, EmploymentRecord.id == EmployeeFeedback.employment_id)
        .outerjoin(InterviewExperience, InterviewExperience.employment_id == EmploymentRecord.id)
        .where(
            EmploymentRecord.company == company, EmployeeFeedback.moderation_status == "approved"
        )
    ).all()
    sample_count = len(rows)
    if sample_count < min_samples:
        return {
            "company": company,
            "sample_count": sample_count,
            "minimum_samples": min_samples,
            "publishable": False,
            "message": "审核通过的匿名样本不足，暂不公开企业评价明细。",
        }
    keys = sorted(EMPLOYEE_SCORE_KEYS)
    averages = {
        key: round(
            sum(json.loads(feedback.scores_json)[key] for feedback, _, _ in rows) / sample_count, 1
        )
        for key in keys
    }
    advice = [
        interview.advice
        for _, _, interview in rows
        if interview is not None and interview.moderation_status == "approved" and interview.advice
    ][:8]
    requirements = [feedback.requirements for feedback, _, _ in rows if feedback.requirements][:8]
    return {
        "company": company,
        "sample_count": sample_count,
        "minimum_samples": min_samples,
        "publishable": True,
        "overall_score": round(
            sum(feedback.overall_score for feedback, _, _ in rows) / sample_count, 1
        ),
        "dimension_scores": averages,
        "recommend_rate": round(
            sum(feedback.would_recommend for feedback, _, _ in rows) * 100 / sample_count
        ),
        "requirements": requirements,
        "interview_advice": advice,
    }


def counselor_quality_overview(db: Session, *, counselor: User) -> dict[str, object]:
    student_ids = (
        list(
            db.scalars(
                select(User.id).where(User.class_id == counselor.class_id, User.role == "student")
            ).all()
        )
        if counselor.role.value != "admin"
        else list(db.scalars(select(User.id).where(User.role == "student")).all())
    )
    if not student_ids:
        return {
            "metrics": {"employed": 0, "followups_due": 0, "pending_moderation": 0},
            "employments": [],
            "pending_feedback": [],
            "companies": [],
        }
    employments = db.scalars(
        select(EmploymentRecord)
        .where(EmploymentRecord.student_id.in_(student_ids))
        .order_by(EmploymentRecord.onboard_date.desc())
        .limit(200)
    ).all()
    employment_ids = [item.id for item in employments]
    due = int(
        db.scalar(
            select(func.count())
            .select_from(FollowupSurvey)
            .where(
                FollowupSurvey.student_id.in_(student_ids),
                FollowupSurvey.due_date <= date.today(),
                FollowupSurvey.status != "completed",
            )
        )
        or 0
    )
    employee_rows = (
        db.execute(
            select(EmployeeFeedback, EmploymentRecord, User)
            .join(EmploymentRecord, EmploymentRecord.id == EmployeeFeedback.employment_id)
            .join(User, User.id == EmploymentRecord.student_id)
            .where(
                EmployeeFeedback.employment_id.in_(employment_ids),
                EmployeeFeedback.moderation_status == "pending",
            )
        ).all()
        if employment_ids
        else []
    )
    employer_rows = (
        db.execute(
            select(EmployerReview, EmploymentRecord, User)
            .join(EmploymentRecord, EmploymentRecord.id == EmployerReview.employment_id)
            .join(User, User.id == EmploymentRecord.student_id)
            .where(
                EmployerReview.employment_id.in_(employment_ids),
                EmployerReview.moderation_status == "pending",
            )
        ).all()
        if employment_ids
        else []
    )
    interview_rows = (
        db.execute(
            select(InterviewExperience, EmploymentRecord, User)
            .join(EmploymentRecord, EmploymentRecord.id == InterviewExperience.employment_id)
            .join(User, User.id == EmploymentRecord.student_id)
            .where(
                InterviewExperience.employment_id.in_(employment_ids),
                InterviewExperience.moderation_status == "pending",
            )
        ).all()
        if employment_ids
        else []
    )
    pending = [
        {
            "id": item.id,
            "type": kind,
            "student_name": student.display_name,
            "company": employment.company,
            "overall_score": getattr(item, "overall_score", None),
            "content": (
                getattr(item, "experience", None)
                or getattr(item, "strengths", None)
                or getattr(item, "advice", None)
                or ""
            )[:1000],
        }
        for kind, rows in (
            ("employee", employee_rows),
            ("employer", employer_rows),
            ("interview", interview_rows),
        )
        for item, employment, student in rows
    ]
    company_counts = db.execute(
        select(EmploymentRecord.company, func.count(EmploymentRecord.id))
        .where(EmploymentRecord.student_id.in_(student_ids))
        .group_by(EmploymentRecord.company)
        .order_by(func.count(EmploymentRecord.id).desc(), EmploymentRecord.company)
        .limit(20)
    ).all()
    users = {
        item.id: item for item in db.scalars(select(User).where(User.id.in_(student_ids))).all()
    }
    return {
        "metrics": {
            "employed": sum(item.status == "employed" for item in employments),
            "followups_due": due,
            "pending_moderation": len(pending),
        },
        "employments": [
            {
                "id": item.id,
                "student_id": item.student_id,
                "student_name": users[item.student_id].display_name
                if item.student_id in users
                else "学生",
                "company": item.company,
                "job_title": item.job_title,
                "onboard_date": item.onboard_date.isoformat(),
                "status": item.status,
            }
            for item in employments
        ],
        "pending_feedback": pending,
        "companies": [
            {"company": company, "employment_count": int(count)}
            for company, count in company_counts
        ],
    }


def moderate_feedback(
    db: Session, *, reviewer: User, feedback_type: str, feedback_id: str, decision: str, reason: str
) -> None:
    models = {
        "employee": EmployeeFeedback,
        "employer": EmployerReview,
        "interview": InterviewExperience,
    }
    model = models.get(feedback_type)
    if model is None or decision not in {"approved", "rejected", "withdrawn"}:
        raise AppError(422, "moderation_invalid", "审核参数无效")
    item = db.get(model, feedback_id)
    if item is None:
        raise AppError(404, "feedback_not_found", "评价记录不存在")
    employment = db.get(EmploymentRecord, item.employment_id)
    student = db.get(User, employment.student_id if employment else "")
    if (
        employment is None
        or student is None
        or (reviewer.role.value != "admin" and reviewer.class_id != student.class_id)
    ):
        raise AppError(403, "forbidden", "无权审核该评价")
    item.moderation_status = decision
    db.add(
        FeedbackModeration(
            feedback_type=feedback_type,
            feedback_id=feedback_id,
            reviewer_id=reviewer.id,
            decision=decision,
            reason=reason,
        )
    )
    db.commit()
