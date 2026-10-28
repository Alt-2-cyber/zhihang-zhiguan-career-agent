import hashlib
import json
from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.base import AgentGateway
from app.core.errors import AppError
from app.core.models import utc_now
from app.growth.models import (
    Course,
    LearningExam,
    LearningExamQuestion,
    LearningExamSubmission,
    LearningMistake,
    LearningPlan,
    LearningTask,
    QuestionBankItem,
    QuestionBankReview,
    QuestionFavorite,
    SkillGap,
)
from app.workplace.models import SimulationScenario, SimulationSession

OPTION_KEYS = ("A", "B", "C", "D")

SKILL_ALIASES = {
    "\u9879\u76ee\u8868\u8fbe": "\u9762\u8bd5\u8868\u8fbe",
    "\u9762\u8bd5\u590d\u76d8": "\u9762\u8bd5\u8868\u8fbe",
    "star\u8868\u8fbe": "\u9762\u8bd5\u8868\u8fbe",
    "\u6c9f\u901a\u8868\u8fbe": "\u9762\u8bd5\u8868\u8fbe",
    "\u6307\u6807\u62c6\u89e3": "\u4e1a\u52a1\u6307\u6807\u62c6\u89e3",
    "\u4e1a\u52a1\u5206\u6790": "\u4e1a\u52a1\u6307\u6807\u62c6\u89e3",
}


def _canonical_skill(value: str) -> str:
    normalized = "".join(value.strip().casefold().split())
    return SKILL_ALIASES.get(normalized, normalized)


def _loads_list(raw: str | None) -> list[object]:
    if not raw:
        return []
    value = json.loads(raw)
    return value if isinstance(value, list) else []


def _as_utc(value: datetime) -> datetime:
    """Normalize SQLite's naive DateTime values before deadline arithmetic."""

    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def serialize_course(course: Course) -> dict[str, object]:
    return {
        "id": course.id,
        "title": course.title,
        "provider": course.provider,
        "source_url": course.source_url,
        "delivery_mode": course.delivery_mode,
        "duration_minutes": course.duration_minutes,
        "skills": _loads_list(course.skills_json),
        "description": course.description,
        "status": course.status,
    }


def serialize_task(task: LearningTask, course: Course | None = None) -> dict[str, object]:
    return {
        "id": task.id,
        "plan_id": task.plan_id,
        "course_id": task.course_id,
        "course_title": course.title if course else None,
        "skill_name": task.skill_name,
        "title": task.title,
        "due_date": task.due_date.isoformat(),
        "acceptance_criteria": task.acceptance_criteria,
        "status": task.status,
        "evidence_url": task.evidence_url,
        "completion_note": task.completion_note,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "updated_at": task.updated_at.isoformat(),
    }


def serialize_exam(exam: LearningExam) -> dict[str, object]:
    started_at = _as_utc(exam.started_at) if exam.started_at is not None else None
    deadline = started_at + timedelta(minutes=exam.duration_minutes) if started_at else None
    remaining_seconds = (
        max(0, int((deadline - utc_now()).total_seconds())) if deadline is not None else None
    )
    status = "expired" if exam.status == "in_progress" and remaining_seconds == 0 else exam.status
    return {
        "id": exam.id,
        "student_id": exam.student_id,
        "course_id": exam.course_id,
        "task_id": exam.task_id,
        "title": exam.title,
        "skill_name": exam.skill_name,
        "generated_by": exam.generated_by,
        "prompt_version": exam.prompt_version,
        "source_context": json.loads(exam.source_context_json or "{}"),
        "generation_error": exam.generation_error,
        "status": status,
        "question_count": exam.question_count,
        "passing_score": exam.passing_score,
        "duration_minutes": exam.duration_minutes,
        "started_at": started_at.isoformat() if started_at else None,
        "expires_at": deadline.isoformat() if deadline else None,
        "remaining_seconds": remaining_seconds,
        "latest_score": exam.latest_score,
        "latest_passed": exam.latest_passed,
        "submitted_at": exam.submitted_at.isoformat() if exam.submitted_at else None,
        "created_at": exam.created_at.isoformat(),
        "updated_at": exam.updated_at.isoformat(),
    }


def serialize_question(question: LearningExamQuestion, *, reveal_answer: bool = False) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": question.id,
        "sequence": question.sequence,
        "question_type": question.question_type,
        "prompt": question.prompt,
        "options": _loads_list(question.options_json),
    }
    if reveal_answer:
        payload["correct_answer"] = question.correct_answer
        payload["explanation"] = question.explanation
    return payload


def serialize_question_bank_item(item: QuestionBankItem) -> dict[str, object]:
    return {
        "id": item.id,
        "skill_name": item.skill_name,
        "course_id": item.course_id,
        "prompt": item.prompt,
        "options": _loads_list(item.options_json),
        "correct_answer": item.correct_answer,
        "explanation": item.explanation,
        "source": item.source,
        "generated_by": item.generated_by,
        "prompt_version": item.prompt_version,
        "content_hash": item.content_hash,
        "status": item.status,
        "reviewed_by": item.reviewed_by,
        "reviewed_at": item.reviewed_at.isoformat() if item.reviewed_at else None,
        "review_reason": item.review_reason,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def list_question_bank(
    db: Session,
    *,
    status: str | None = None,
    skill_name: str | None = None,
    limit: int = 100,
) -> list[dict[str, object]]:
    statement = select(QuestionBankItem).order_by(
        QuestionBankItem.status,
        QuestionBankItem.updated_at.desc(),
        QuestionBankItem.id,
    )
    if status:
        statement = statement.where(QuestionBankItem.status == status)
    if skill_name:
        statement = statement.where(QuestionBankItem.skill_name == skill_name[:100])
    return [
        serialize_question_bank_item(item)
        for item in db.scalars(statement.limit(max(1, min(limit, 500)))).all()
    ]


def review_question_bank_item(
    db: Session,
    *,
    item_id: str,
    reviewer_id: str,
    decision: str,
    reason: str,
    commit: bool = True,
) -> dict[str, object]:
    item = db.get(QuestionBankItem, item_id)
    if item is None:
        raise AppError(404, "question_bank_item_not_found", "题库题目不存在")
    if decision not in {"approved", "rejected", "retired"}:
        raise AppError(422, "question_bank_decision_invalid", "题库审核决定无效")
    reason = reason.strip()
    if not reason:
        raise AppError(422, "question_bank_reason_required", "审核必须填写理由")
    previous_status = item.status
    item.status = decision
    item.reviewed_by = reviewer_id
    item.reviewed_at = utc_now()
    item.review_reason = reason[:1_000]
    db.add(
        QuestionBankReview(
            item_id=item.id,
            reviewer_id=reviewer_id,
            previous_status=previous_status,
            decision=decision,
            reason=reason[:1_000],
        )
    )
    if commit:
        db.commit()
        db.refresh(item)
    else:
        db.flush()
    return serialize_question_bank_item(item)


def serialize_exam_detail(
    exam: LearningExam,
    questions: Iterable[LearningExamQuestion],
    *,
    reveal_answer: bool = False,
) -> dict[str, object]:
    payload = serialize_exam(exam)
    payload["questions"] = [
        serialize_question(question, reveal_answer=reveal_answer) for question in questions
    ]
    return payload


def serialize_submission(submission: LearningExamSubmission) -> dict[str, object]:
    return {
        "id": submission.id,
        "exam_id": submission.exam_id,
        "student_id": submission.student_id,
        "answers": json.loads(submission.answers_json),
        "score": submission.score,
        "passed": submission.passed,
        "results": json.loads(submission.results_json),
        "submitted_at": submission.submitted_at.isoformat(),
    }


def _get_owned_question(
    db: Session, *, student_id: str, question_id: str
) -> tuple[LearningExamQuestion, LearningExam]:
    row = db.execute(
        select(LearningExamQuestion, LearningExam)
        .join(LearningExam, LearningExam.id == LearningExamQuestion.exam_id)
        .where(
            LearningExamQuestion.id == question_id,
            LearningExam.student_id == student_id,
        )
    ).one_or_none()
    if row is None:
        raise AppError(404, "learning_question_not_found", "题目不存在或无权访问")
    return row


def toggle_question_favorite(
    db: Session, *, student_id: str, question_id: str
) -> dict[str, object]:
    _get_owned_question(db, student_id=student_id, question_id=question_id)
    existing = db.scalar(
        select(QuestionFavorite).where(
            QuestionFavorite.student_id == student_id,
            QuestionFavorite.question_id == question_id,
        )
    )
    if existing:
        db.delete(existing)
        db.commit()
        return {"question_id": question_id, "favorited": False}
    db.add(QuestionFavorite(student_id=student_id, question_id=question_id))
    db.commit()
    return {"question_id": question_id, "favorited": True}


def list_learning_review(db: Session, *, student_id: str) -> dict[str, object]:
    favorite_rows = db.execute(
        select(QuestionFavorite, LearningExamQuestion, LearningExam)
        .join(LearningExamQuestion, LearningExamQuestion.id == QuestionFavorite.question_id)
        .join(LearningExam, LearningExam.id == LearningExamQuestion.exam_id)
        .where(QuestionFavorite.student_id == student_id, LearningExam.student_id == student_id)
        .order_by(QuestionFavorite.updated_at.desc())
        .limit(100)
    ).all()
    mistakes = db.scalars(
        select(LearningMistake)
        .where(LearningMistake.student_id == student_id)
        .order_by(LearningMistake.status, LearningMistake.updated_at.desc())
        .limit(100)
    ).all()
    return {
        "favorites": [
            {
                "id": favorite.id,
                "question_id": question.id,
                "exam_id": exam.id,
                "skill_name": exam.skill_name,
                "prompt": question.prompt,
                "options": _loads_list(question.options_json),
                "correct_answer": question.correct_answer,
                "explanation": question.explanation,
            }
            for favorite, question, exam in favorite_rows
        ],
        "mistakes": [
            {
                "id": item.id,
                "question_id": item.question_id,
                "exam_id": item.exam_id,
                "skill_name": item.skill_name,
                "selected_answer": item.selected_answer,
                "correct_answer": item.correct_answer,
                "explanation": item.explanation,
                "status": item.status,
                "last_submission_at": item.last_submission_at.isoformat(),
            }
            for item in mistakes
        ],
    }


def _build_skill_analytics(
    *,
    gaps: list[SkillGap],
    completed_tasks: list[LearningTask],
    submissions: list[tuple[LearningExamSubmission, LearningExam]],
    training_rows: list[tuple[SimulationSession, SimulationScenario]],
) -> list[dict[str, object]]:
    """Compute a bounded, inspectable capability score from persisted evidence."""

    latest_exam_by_skill: dict[str, LearningExamSubmission] = {}
    for submission, exam in submissions:
        key = _canonical_skill(exam.skill_name)
        previous = latest_exam_by_skill.get(key)
        if previous is None or submission.submitted_at > previous.submitted_at:
            latest_exam_by_skill[key] = submission

    latest_training_by_skill: dict[str, SimulationSession] = {}
    for session, scenario in training_rows:
        if session.score is None:
            continue
        for competency in _loads_list(scenario.competencies_json):
            key = _canonical_skill(str(competency))
            previous = latest_training_by_skill.get(key)
            if previous is None or (session.completed_at or session.updated_at) > (
                previous.completed_at or previous.updated_at
            ):
                latest_training_by_skill[key] = session

        # Presentation-oriented sessions are direct evidence for expression skills.
        if session.mode in {"stress_interview", "presentation_defense"}:
            key = _canonical_skill("\u9762\u8bd5\u8868\u8fbe")
            previous = latest_training_by_skill.get(key)
            if previous is None or (session.completed_at or session.updated_at) > (
                previous.completed_at or previous.updated_at
            ):
                latest_training_by_skill[key] = session

    analytics: list[dict[str, object]] = []
    for gap in gaps:
        key = _canonical_skill(gap.skill_name)
        baseline = gap.current_level
        matched_tasks = [task for task in completed_tasks if _canonical_skill(task.skill_name) == key]
        latest_exam = latest_exam_by_skill.get(key)
        latest_training = latest_training_by_skill.get(key)

        current = baseline
        sources = ["diagnostic_baseline"]
        if latest_exam is not None:
            current = round(current * 0.45 + latest_exam.score * 0.55)
            sources.append("latest_exam")
        if latest_training is not None and latest_training.score is not None:
            current = round(current * 0.7 + latest_training.score * 0.3)
            sources.append("latest_training")
        if matched_tasks:
            # Completing an evidence-bearing task is supporting evidence, never a large score jump.
            current += min(6, len(matched_tasks) * 2)
            sources.append("learning_evidence")
        current = max(0, min(100, current))

        evidence_count = len(matched_tasks) + int(latest_exam is not None) + int(
            latest_training is not None
        )
        if evidence_count == 0:
            data_status = "baseline"
            score_reason = "\u5f53\u524d\u65e0\u6709\u6548\u5b66\u4e60\u6216\u6d4b\u8bc4\u8bb0\u5f55\uff0c\u663e\u793a\u521d\u59cb\u8bca\u65ad\u57fa\u7ebf\u3002"
        elif latest_exam is not None or latest_training is not None:
            data_status = "evidence_based"
            score_reason = "\u5df2\u7efc\u5408\u6700\u8fd1\u6d4b\u9a8c/\u8bad\u7ec3\u6210\u7ee9\u4e0e\u5df2\u63d0\u4ea4\u7684\u5b66\u4e60\u8bc1\u636e\u3002"
        else:
            data_status = "task_evidence"
            score_reason = "\u5df2\u7eb3\u5165\u5b8c\u6210\u4efb\u52a1\u7684\u8bc1\u636e\uff1b\u5b8c\u6210\u6d4b\u9a8c\u6216\u4e13\u9879\u8bad\u7ec3\u540e\u53ef\u83b7\u5f97\u66f4\u9ad8\u7f6e\u4fe1\u5ea6\u3002"

        analytics.append(
            {
                "skill_name": gap.skill_name,
                "baseline": baseline,
                "current": current,
                "target": gap.target_level,
                "gap": max(0, gap.target_level - current),
                "evidence_count": evidence_count,
                "baseline_evidence_count": len(_loads_list(gap.evidence_json)),
                "latest_exam_score": latest_exam.score if latest_exam else None,
                "latest_training_score": latest_training.score if latest_training else None,
                "score_sources": sources,
                "score_reason": score_reason,
                "data_status": data_status,
                "status": gap.status,
            }
        )
    return analytics


def get_growth_overview(db: Session, student_id: str) -> dict[str, object]:
    gaps = db.scalars(
        select(SkillGap)
        .where(SkillGap.student_id == student_id)
        .order_by(SkillGap.target_level.desc(), SkillGap.skill_name)
    ).all()
    plan = db.scalar(
        select(LearningPlan)
        .where(LearningPlan.student_id == student_id, LearningPlan.status == "active")
        .order_by(LearningPlan.updated_at.desc())
    )
    rows = db.execute(
        select(LearningTask, Course)
        .outerjoin(Course, Course.id == LearningTask.course_id)
        .where(LearningTask.student_id == student_id)
        .order_by(LearningTask.status, LearningTask.due_date, LearningTask.id)
        .limit(100)
    ).all()
    tasks = [serialize_task(task, course) for task, course in rows]
    completed = sum(item["status"] == "completed" for item in tasks)
    completed_task_rows = [
        task
        for task, _course in rows
        if task.status == "completed" and (task.completion_note or task.evidence_url)
    ]
    submissions = db.execute(
        select(LearningExamSubmission, LearningExam)
        .join(LearningExam, LearningExam.id == LearningExamSubmission.exam_id)
        .where(LearningExamSubmission.student_id == student_id)
        .order_by(LearningExamSubmission.submitted_at.desc())
        .limit(200)
    ).all()
    current_week = date.today() - timedelta(days=date.today().weekday())
    trend_weeks = [current_week - timedelta(days=7 * offset) for offset in reversed(range(8))]
    trend = {
        week.isoformat(): {"scores": [], "completed_tasks": 0} for week in trend_weeks
    }
    for submission, _exam in submissions:
        week = submission.submitted_at.date() - timedelta(
            days=submission.submitted_at.date().weekday()
        )
        if week.isoformat() in trend:
            trend[week.isoformat()]["scores"].append(submission.score)
    for task in db.scalars(
        select(LearningTask)
        .where(
            LearningTask.student_id == student_id,
            LearningTask.status == "completed",
            LearningTask.completed_at.is_not(None),
        )
        .limit(500)
    ).all():
        if task.completed_at is None:
            continue
        completed_week = task.completed_at.date() - timedelta(days=task.completed_at.date().weekday())
        if completed_week.isoformat() in trend:
            trend[completed_week.isoformat()]["completed_tasks"] += 1
    training_rows = db.execute(
        select(SimulationSession, SimulationScenario)
        .join(SimulationScenario, SimulationScenario.id == SimulationSession.scenario_id)
        .where(
            SimulationSession.student_id == student_id,
            SimulationSession.status == "completed",
            SimulationSession.score.is_not(None),
        )
        .order_by(SimulationSession.completed_at.desc())
        .limit(100)
    ).all()
    skill_analytics = _build_skill_analytics(
        gaps=gaps,
        completed_tasks=completed_task_rows,
        submissions=submissions,
        training_rows=training_rows,
    )
    analytics_by_skill = {str(item["skill_name"]): item for item in skill_analytics}
    return {
        "plan": None
        if plan is None
        else {
            "id": plan.id,
            "target_role": plan.target_role,
            "rationale": plan.rationale,
            "status": plan.status,
            "version": plan.version,
        },
        "skill_gaps": [
            {
                "id": item.id,
                "skill_name": item.skill_name,
                "current_level": analytics_by_skill[item.skill_name]["current"],
                "baseline_level": item.current_level,
                "target_level": item.target_level,
                "evidence": _loads_list(item.evidence_json),
                "evidence_count": analytics_by_skill[item.skill_name]["evidence_count"],
                "data_status": analytics_by_skill[item.skill_name]["data_status"],
                "score_reason": analytics_by_skill[item.skill_name]["score_reason"],
                "status": item.status,
            }
            for item in gaps
        ],
        "tasks": tasks,
        "metrics": {
            "total_tasks": len(tasks),
            "completed_tasks": completed,
            "completion_rate": round(completed * 100 / len(tasks)) if tasks else 0,
        },
        "analytics": {
            "rubric_version": "growth-analytics-v2",
            "radar": skill_analytics,
            "weak_points": sorted(
                skill_analytics,
                key=lambda item: (-int(item["gap"]), str(item["skill_name"])),
            )[:8],
            "trend": [
                {
                    "period": period,
                    "average_score": round(sum(values["scores"]) / len(values["scores"]))
                    if values["scores"]
                    else None,
                    "exam_count": len(values["scores"]),
                    "completed_tasks": values["completed_tasks"],
                }
                for period, values in trend.items()
            ],
        },
    }


def list_learning_exams(db: Session, student_id: str) -> list[dict[str, object]]:
    exams = db.scalars(
        select(LearningExam)
        .where(LearningExam.student_id == student_id)
        .order_by(LearningExam.updated_at.desc(), LearningExam.created_at.desc())
        .limit(50)
    ).all()
    return [serialize_exam(exam) for exam in exams]


def _get_owned_exam(db: Session, *, student_id: str, exam_id: str) -> LearningExam:
    exam = db.get(LearningExam, exam_id)
    if exam is None or exam.student_id != student_id:
        raise AppError(404, "learning_exam_not_found", "学习考试不存在")
    return exam


def get_learning_exam_detail(db: Session, *, student_id: str, exam_id: str) -> dict[str, object]:
    exam = _get_owned_exam(db, student_id=student_id, exam_id=exam_id)
    questions = db.scalars(
        select(LearningExamQuestion)
        .where(LearningExamQuestion.exam_id == exam.id)
        .order_by(LearningExamQuestion.sequence)
    ).all()
    submission = db.scalars(
        select(LearningExamSubmission)
        .where(
            LearningExamSubmission.exam_id == exam.id,
            LearningExamSubmission.student_id == student_id,
        )
        .order_by(LearningExamSubmission.submitted_at.desc(), LearningExamSubmission.created_at.desc())
    ).first()
    payload = serialize_exam_detail(exam, questions)
    payload["submission"] = serialize_submission(submission) if submission is not None else None
    return payload


def start_learning_exam(
    db: Session,
    *,
    student_id: str,
    exam_id: str,
    commit: bool = True,
) -> dict[str, object]:
    exam = _get_owned_exam(db, student_id=student_id, exam_id=exam_id)
    if exam.status in {"passed", "submitted", "expired"}:
        raise AppError(409, "learning_exam_unavailable", "\u8be5\u6d4b\u9a8c\u5df2\u7ed3\u675f\uff0c\u8bf7\u65b0\u5efa\u4e00\u573a\u6d4b\u9a8c")
    if exam.status not in {"generated", "in_progress"}:
        raise AppError(409, "learning_exam_unavailable", "\u6d4b\u9a8c\u9898\u76ee\u5c1a\u672a\u51c6\u5907\u5b8c\u6210")
    if exam.started_at is None:
        exam.started_at = utc_now()
        exam.status = "in_progress"
    else:
        deadline = _as_utc(exam.started_at) + timedelta(minutes=exam.duration_minutes)
        if deadline <= utc_now():
            exam.status = "expired"
            if commit:
                db.commit()
            else:
                db.flush()
            raise AppError(409, "learning_exam_expired", "\u6d4b\u9a8c\u65f6\u95f4\u5df2\u7ed3\u675f")
    if commit:
        db.commit()
    else:
        db.flush()
    return get_learning_exam_detail(db, student_id=student_id, exam_id=exam.id)


def _resolve_course_and_task(
    db: Session,
    *,
    student_id: str,
    course_id: str | None,
    task_id: str | None,
) -> tuple[Course | None, LearningTask | None]:
    task: LearningTask | None = None
    if task_id:
        task = db.get(LearningTask, task_id)
        if task is None or task.student_id != student_id:
            raise AppError(404, "learning_task_not_found", "学习任务不存在")
        course_id = course_id or task.course_id

    course: Course | None = None
    if course_id:
        course = db.get(Course, course_id)
        if course is None or course.status != "active":
            raise AppError(404, "course_not_found", "课程不存在或不可用")
    return course, task


def _build_question_pool(*, course: Course | None, task: LearningTask | None, skill_name: str) -> list[dict[str, object]]:
    course_title = course.title if course else "当前学习资源"
    task_title = task.title if task else "本次学习目标"
    course_skills = [str(item) for item in _loads_list(course.skills_json if course else "[]")]
    support_skills = "、".join(course_skills[:3]) if course_skills else skill_name
    return [
        {
            "prompt": f"围绕“{course_title}”，学习 {skill_name} 时最应该先确认什么？",
            "options": [
                {"key": "A", "text": "目标岗位要求、业务场景和验收标准"},
                {"key": "B", "text": "只把课程视频全部看完"},
                {"key": "C", "text": "优先追求最复杂的模型或工具"},
                {"key": "D", "text": "暂时不记录学习证据"},
            ],
            "answer": "A",
            "explanation": "就业学习任务要从岗位能力和验收证据出发，不能只停留在观看课程。",
        },
        {
            "prompt": f"完成“{task_title}”后，哪类材料最能作为学习任务验收证据？",
            "options": [
                {"key": "A", "text": "一句“我已经学完了”"},
                {"key": "B", "text": "截图、练习结果、复盘说明或可访问成果链接"},
                {"key": "C", "text": "收藏课程链接但不练习"},
                {"key": "D", "text": "只记录学习时长"},
            ],
            "answer": "B",
            "explanation": "系统要求学习闭环可核验，成果证据需要能证明实际完成情况和质量。",
        },
        {
            "prompt": f"如果目标岗位要求 {support_skills}，但简历证据不足，下一步最合理的是？",
            "options": [
                {"key": "A", "text": "继续扩大投递，不调整材料"},
                {"key": "B", "text": "补一个小项目或练习，并把过程、结果写进简历"},
                {"key": "C", "text": "隐藏相关能力差距"},
                {"key": "D", "text": "只让 Agent 给出鼓励性回复"},
            ],
            "answer": "B",
            "explanation": "能力差距要转化为可展示证据，才能提升岗位匹配和面试表达。",
        },
        {
            "prompt": f"学习 {skill_name} 的过程中，Agent 给出的计划最应该如何被使用？",
            "options": [
                {"key": "A", "text": "完全不需要人工确认"},
                {"key": "B", "text": "结合个人目标确认后执行，并持续记录进度"},
                {"key": "C", "text": "只保留最容易完成的任务"},
                {"key": "D", "text": "把计划当作一次性文本，不进入系统状态"},
            ],
            "answer": "B",
            "explanation": "本项目强调人机协同：Agent 规划，学生确认执行，过程和结果进入系统闭环。",
        },
        {
            "prompt": f"学习完“{course_title}”后，如何判断它真的提升了求职竞争力？",
            "options": [
                {"key": "A", "text": "是否形成了可用于简历、面试或投递匹配的证据"},
                {"key": "B", "text": "视频标题是否足够热门"},
                {"key": "C", "text": "课程时长是否越长越好"},
                {"key": "D", "text": "是否没有任何错题"},
            ],
            "answer": "A",
            "explanation": "就业导向的学习要看能否支撑画像、简历、岗位匹配和面试表达。",
        },
        {
            "prompt": f"如果本次 {skill_name} 测验没有通过，系统最合理的下一步是？",
            "options": [
                {"key": "A", "text": "删除学习记录"},
                {"key": "B", "text": "保留成绩和错题解释，继续安排补强任务"},
                {"key": "C", "text": "自动代替学生投递岗位"},
                {"key": "D", "text": "把未通过记录隐藏起来"},
            ],
            "answer": "B",
            "explanation": "测验记录要服务后续改进，失败也应成为学习计划调整的依据。",
        },
    ]


def create_learning_exam(
    db: Session,
    *,
    student_id: str,
    course_id: str | None,
    task_id: str | None,
    skill_name: str | None,
    question_count: int,
    gateway: AgentGateway,
    commit: bool = True,
) -> dict[str, object]:
    course, task = _resolve_course_and_task(
        db,
        student_id=student_id,
        course_id=course_id,
        task_id=task_id,
    )
    if skill_name is None:
        if task is not None:
            skill_name = task.skill_name
        else:
            skills = [str(item) for item in _loads_list(course.skills_json if course else "[]")]
            skill_name = skills[0] if skills else "就业能力"
    question_count = max(3, min(question_count, 10))
    title_source = course.title if course else (task.title if task else skill_name)
    exam = LearningExam(
        student_id=student_id,
        course_id=course.id if course else None,
        task_id=task.id if task else None,
        title=f"{title_source} · AI 出题考试",
        skill_name=skill_name,
        question_count=question_count,
        passing_score=60,
        duration_minutes=max(5, min(question_count * 4, 45)),
    )
    source_context = {
        "course": serialize_course(course) if course else None,
        "task": serialize_task(task, course) if task else None,
        "skill_name": skill_name,
    }
    exam.generated_by = "pending"
    exam.prompt_version = "exam-v1"
    exam.source_context_json = json.dumps(source_context, ensure_ascii=False)
    exam.status = "generating"
    db.add(exam)
    db.flush()
    try:
        generation = gateway.generate_learning_exam(
            skill_name=skill_name,
            context=source_context,
            question_count=question_count,
        )
        if len(generation.questions) < question_count:
            raise ValueError("exam provider returned fewer questions than requested")
    except Exception as error:
        exam.status = "generation_failed"
        exam.generation_error = str(getattr(error, "code", None) or type(error).__name__)[:500]
        if commit:
            db.commit()
        raise AppError(
            503,
            "learning_exam_generation_failed",
            "AI 出题服务暂不可用，请稍后重试",
        ) from error

    exam.generated_by = generation.provider
    exam.prompt_version = generation.prompt_version
    exam.status = "generated"
    exam.generation_error = None
    for sequence, spec in enumerate(generation.questions[:question_count], start=1):
        options_json = json.dumps(
            [item.model_dump(mode="json") for item in spec.options],
            ensure_ascii=False,
        )
        content_hash = hashlib.sha256(
            json.dumps(
                {
                    "prompt": spec.prompt,
                    "options": json.loads(options_json),
                    "answer": spec.correct_answer,
                    "explanation": spec.explanation,
                },
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        bank_item = QuestionBankItem(
            skill_name=skill_name,
            course_id=course.id if course else None,
            prompt=spec.prompt,
            options_json=options_json,
            correct_answer=spec.correct_answer,
            explanation=spec.explanation,
            source="agent",
            generated_by=generation.provider,
            prompt_version=generation.prompt_version,
            content_hash=content_hash,
            status="pending_review",
        )
        db.add(bank_item)
        db.flush()
        db.add(
            LearningExamQuestion(
                exam_id=exam.id,
                sequence=sequence,
                question_type=spec.question_type,
                prompt=spec.prompt,
                options_json=options_json,
                correct_answer=spec.correct_answer,
                explanation=spec.explanation,
                question_bank_item_id=bank_item.id,
            )
        )
    if commit:
        db.commit()
        db.refresh(exam)
    else:
        db.flush()
    return get_learning_exam_detail(db, student_id=student_id, exam_id=exam.id)


def submit_learning_exam(
    db: Session,
    *,
    student_id: str,
    exam_id: str,
    answers: dict[str, str],
    commit: bool = True,
) -> dict[str, object]:
    exam = _get_owned_exam(db, student_id=student_id, exam_id=exam_id)
    if exam.status in {"passed", "submitted", "expired"}:
        raise AppError(409, "learning_exam_unavailable", "\u8be5\u6d4b\u9a8c\u5df2\u7ed3\u675f\uff0c\u8bf7\u65b0\u5efa\u4e00\u573a\u6d4b\u9a8c")
    if exam.started_at is None:
        raise AppError(409, "learning_exam_not_started", "\u8bf7\u5148\u5f00\u59cb\u6d4b\u9a8c\uff0c\u8ba1\u65f6\u4ece\u5f00\u59cb\u540e\u624d\u4f1a\u5f00\u542f")
    deadline = _as_utc(exam.started_at) + timedelta(minutes=exam.duration_minutes)
    if deadline <= utc_now():
        exam.status = "expired"
        if commit:
            db.commit()
        else:
            db.flush()
        raise AppError(409, "learning_exam_expired", "\u6d4b\u9a8c\u65f6\u95f4\u5df2\u7ed3\u675f")
    questions = db.scalars(
        select(LearningExamQuestion)
        .where(LearningExamQuestion.exam_id == exam.id)
        .order_by(LearningExamQuestion.sequence)
    ).all()
    if not questions:
        raise AppError(409, "learning_exam_questions_missing", "考试题目不存在，请重新生成")

    normalized_answers = {key: value.strip().upper() for key, value in answers.items()}
    correct_count = 0
    results: list[dict[str, object]] = []
    for question in questions:
        selected = normalized_answers.get(question.id) or normalized_answers.get(str(question.sequence))
        selected = selected if selected in OPTION_KEYS else ""
        is_correct = selected == question.correct_answer
        if is_correct:
            correct_count += 1
        results.append(
            {
                "question_id": question.id,
                "sequence": question.sequence,
                "prompt": question.prompt,
                "selected_answer": selected,
                "correct_answer": question.correct_answer,
                "is_correct": is_correct,
                "explanation": question.explanation,
                "options": _loads_list(question.options_json),
            }
        )
        mistake = db.scalar(
            select(LearningMistake).where(
                LearningMistake.student_id == student_id,
                LearningMistake.question_id == question.id,
            )
        )
        if is_correct:
            if mistake is not None:
                mistake.status = "resolved"
                mistake.selected_answer = selected
                mistake.last_submission_at = utc_now()
        elif mistake is None:
            db.add(
                LearningMistake(
                    student_id=student_id,
                    exam_id=exam.id,
                    question_id=question.id,
                    skill_name=exam.skill_name,
                    selected_answer=selected,
                    correct_answer=question.correct_answer,
                    explanation=question.explanation,
                    status="open",
                    last_submission_at=utc_now(),
                )
            )
        else:
            mistake.exam_id = exam.id
            mistake.skill_name = exam.skill_name
            mistake.selected_answer = selected
            mistake.correct_answer = question.correct_answer
            mistake.explanation = question.explanation
            mistake.status = "open"
            mistake.last_submission_at = utc_now()

    score = round(correct_count * 100 / len(questions))
    passed = score >= exam.passing_score
    submitted_at = utc_now()
    submission = LearningExamSubmission(
        exam_id=exam.id,
        student_id=student_id,
        answers_json=json.dumps(normalized_answers, ensure_ascii=False),
        score=score,
        passed=passed,
        results_json=json.dumps(results, ensure_ascii=False),
        submitted_at=submitted_at,
    )
    exam.status = "passed" if passed else "submitted"
    exam.latest_score = score
    exam.latest_passed = passed
    exam.submitted_at = submitted_at
    db.add(submission)
    if commit:
        db.commit()
        db.refresh(submission)
    else:
        db.flush()
    return serialize_submission(submission)


def update_learning_task(
    db: Session,
    *,
    student_id: str,
    task_id: str,
    status: str,
    completion_note: str | None,
    evidence_url: str | None,
    commit: bool = True,
) -> LearningTask:
    task = db.get(LearningTask, task_id)
    if task is None or task.student_id != student_id:
        raise AppError(404, "learning_task_not_found", "学习任务不存在")
    if status == "completed" and not (completion_note or evidence_url):
        raise AppError(422, "learning_evidence_required", "完成学习任务需要填写成果说明或证据链接")
    if status not in {"pending", "in_progress", "completed"}:
        raise AppError(422, "learning_status_invalid", "学习任务状态无效")
    task.status = status
    task.completion_note = completion_note
    task.evidence_url = evidence_url
    task.completed_at = utc_now() if status == "completed" else None
    if commit:
        db.commit()
        db.refresh(task)
    else:
        db.flush()
    return task
