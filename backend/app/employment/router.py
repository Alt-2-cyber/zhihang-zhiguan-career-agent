from datetime import date

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User, UserRole
from app.auth.security import require_roles
from app.core.database import get_db
from app.employment.models import EmploymentRecord
from app.employment.service import (
    counselor_quality_overview,
    create_employer_invitation,
    create_employment,
    employment_summary,
    enterprise_profile,
    moderate_feedback,
    resolve_invitation,
    submit_employee_feedback,
    submit_employer_review,
)

router = APIRouter(prefix="/employment", tags=["employment"])


class EmploymentCreate(BaseModel):
    application_id: str = Field(min_length=36, max_length=36)
    onboard_date: date
    student_consent: bool = False


class ScorePayload(BaseModel):
    scores: dict[str, int]


class EmployerReviewCreate(ScorePayload):
    trial_result: str = Field(min_length=1, max_length=40)
    strengths: str = Field(min_length=10, max_length=4000)
    improvement: str = Field(min_length=10, max_length=4000)
    curriculum_suggestion: str | None = Field(default=None, max_length=4000)


class InterviewExperienceCreate(BaseModel):
    difficulty: int = Field(ge=1, le=5)
    rounds: int = Field(ge=1, le=20)
    process: str = Field(min_length=10, max_length=4000)
    questions: str = Field(min_length=10, max_length=4000)
    advice: str = Field(min_length=10, max_length=4000)


class EmployeeFeedbackCreate(ScorePayload):
    requirements: str = Field(min_length=10, max_length=4000)
    experience: str = Field(min_length=10, max_length=4000)
    recommendation: str = Field(min_length=10, max_length=4000)
    would_recommend: bool
    interview: InterviewExperienceCreate


class ModerationRequest(BaseModel):
    feedback_type: str = Field(pattern="^(employee|employer|interview)$")
    feedback_id: str = Field(min_length=36, max_length=36)
    decision: str = Field(pattern="^(approved|rejected|withdrawn)$")
    reason: str = Field(min_length=2, max_length=500)


@router.get("/records")
def records(
    current_user: User = Depends(require_roles(UserRole.student)), db: Session = Depends(get_db)
) -> list[dict[str, object]]:
    items = db.scalars(
        select(EmploymentRecord)
        .where(EmploymentRecord.student_id == current_user.id)
        .order_by(EmploymentRecord.onboard_date.desc())
        .limit(50)
    ).all()
    return [employment_summary(db, item) for item in items]


@router.post("/records", status_code=status.HTTP_201_CREATED)
def add_record(
    payload: EmploymentCreate,
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = create_employment(
        db,
        student=current_user,
        application_id=payload.application_id,
        onboard_date=payload.onboard_date,
        consent=payload.student_consent,
    )
    return employment_summary(db, item)


@router.post("/records/{employment_id}/employer-invitations", status_code=status.HTTP_201_CREATED)
def invite_employer(
    employment_id: str,
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    invitation, token = create_employer_invitation(
        db, student_id=current_user.id, employment_id=employment_id
    )
    return {
        "invitation_id": invitation.id,
        "token": token,
        "expires_at": invitation.expires_at.isoformat(),
        "warning": "该邀请链接只展示一次，请通过可信渠道发送给企业联系人。",
    }


@router.put("/records/{employment_id}/employee-feedback")
def add_employee_feedback(
    employment_id: str,
    payload: EmployeeFeedbackCreate,
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = submit_employee_feedback(
        db,
        student_id=current_user.id,
        employment_id=employment_id,
        scores=payload.scores,
        requirements=payload.requirements,
        experience=payload.experience,
        recommendation=payload.recommendation,
        would_recommend=payload.would_recommend,
        interview_data=payload.interview.model_dump(),
    )
    return {"id": item.id, "moderation_status": item.moderation_status}


@router.get("/employer-invitations/{token}")
def invitation_info(token: str, db: Session = Depends(get_db)) -> dict[str, object]:
    invitation, employment = resolve_invitation(db, token)
    return {
        "company": employment.company,
        "job_title": employment.job_title,
        "expires_at": invitation.expires_at.isoformat(),
        "dimensions": sorted(
            [
                "role_readiness",
                "professional_skill",
                "learning",
                "communication",
                "delivery_quality",
                "initiative",
                "professionalism",
            ]
        ),
    }


@router.post("/employer-invitations/{token}/review", status_code=status.HTTP_201_CREATED)
def employer_review(
    token: str, payload: EmployerReviewCreate, db: Session = Depends(get_db)
) -> dict[str, object]:
    item = submit_employer_review(
        db,
        token=token,
        scores=payload.scores,
        trial_result=payload.trial_result,
        strengths=payload.strengths,
        improvement=payload.improvement,
        curriculum_suggestion=payload.curriculum_suggestion,
    )
    return {"id": item.id, "status": "submitted", "moderation_status": item.moderation_status}


@router.get("/enterprises/{company}/profile")
def public_enterprise_profile(company: str, db: Session = Depends(get_db)) -> dict[str, object]:
    return enterprise_profile(db, company[:160])


@router.get("/counselor/quality")
def quality(
    current_user: User = Depends(require_roles(UserRole.counselor, UserRole.admin)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return counselor_quality_overview(db, counselor=current_user)


@router.post("/counselor/moderation")
def moderate(
    payload: ModerationRequest,
    current_user: User = Depends(require_roles(UserRole.counselor, UserRole.admin)),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    moderate_feedback(
        db,
        reviewer=current_user,
        feedback_type=payload.feedback_type,
        feedback_id=payload.feedback_id,
        decision=payload.decision,
        reason=payload.reason,
    )
    return {"status": payload.decision}
