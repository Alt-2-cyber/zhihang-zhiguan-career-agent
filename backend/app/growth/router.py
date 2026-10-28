import json
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.service import build_agent_gateway
from app.audit.models import AuditLog
from app.auth.models import User, UserRole
from app.auth.security import require_roles
from app.core.config import get_settings
from app.core.database import get_db
from app.growth.models import Course
from app.growth.service import (
    create_learning_exam,
    get_growth_overview,
    get_learning_exam_detail,
    list_learning_exams,
    list_learning_review,
    list_question_bank,
    review_question_bank_item,
    serialize_course,
    serialize_task,
    start_learning_exam,
    submit_learning_exam,
    toggle_question_favorite,
    update_learning_task,
)

router = APIRouter(prefix="/growth", tags=["growth"])


class LearningTaskUpdate(BaseModel):
    status: Literal["pending", "in_progress", "completed"]
    completion_note: str | None = Field(default=None, max_length=2000)
    evidence_url: str | None = Field(default=None, max_length=1000)


class LearningExamCreate(BaseModel):
    course_id: str | None = None
    task_id: str | None = None
    skill_name: str | None = Field(default=None, max_length=100)
    question_count: int = Field(default=5, ge=3, le=10)


class LearningExamSubmit(BaseModel):
    answers: dict[str, str] = Field(default_factory=dict)


class QuestionBankReviewPayload(BaseModel):
    decision: Literal["approved", "rejected", "retired"]
    reason: str = Field(min_length=1, max_length=1_000)


@router.get("/overview")
def overview(
    current_user: User = Depends(require_roles(UserRole.student)), db: Session = Depends(get_db)
) -> dict[str, object]:
    return get_growth_overview(db, current_user.id)


@router.get("/courses")
def list_courses(
    skill: str | None = None,
    limit: int = 30,
    _user: User = Depends(require_roles(UserRole.student, UserRole.counselor, UserRole.admin)),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    limit = max(1, min(limit, 100))
    statement = select(Course).where(Course.status == "active")
    if skill:
        statement = statement.where(Course.skills_json.ilike(f"%{skill[:100]}%"))
    return [
        serialize_course(item)
        for item in db.scalars(
            statement.order_by(Course.verified_at.desc(), Course.title).limit(limit)
        ).all()
    ]


@router.get("/exams")
def exams(
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    return list_learning_exams(db, current_user.id)


@router.get("/review")
def learning_review(
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return list_learning_review(db, student_id=current_user.id)


@router.get("/question-bank")
def question_bank(
    status: Literal["pending_review", "approved", "rejected", "retired"] | None = None,
    skill_name: str | None = None,
    limit: int = 100,
    _current_user: User = Depends(require_roles(UserRole.counselor, UserRole.admin)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    items = list_question_bank(db, status=status, skill_name=skill_name, limit=limit)
    return {"items": items, "count": len(items)}


@router.post("/question-bank/{item_id}/review")
def review_question_bank(
    item_id: str,
    payload: QuestionBankReviewPayload,
    current_user: User = Depends(require_roles(UserRole.counselor, UserRole.admin)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    result = review_question_bank_item(
        db,
        item_id=item_id,
        reviewer_id=current_user.id,
        decision=payload.decision,
        reason=payload.reason,
    )
    db.add(
        AuditLog(
            user_id=current_user.id,
            action="question_bank.reviewed",
            resource_type="question_bank_item",
            resource_id=item_id,
            details=json.dumps(
                {"decision": payload.decision, "reason": payload.reason},
                ensure_ascii=False,
            ),
        )
    )
    db.commit()
    return result


@router.post("/exams")
def create_exam(
    payload: LearningExamCreate,
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return create_learning_exam(
        db,
        student_id=current_user.id,
        course_id=payload.course_id,
        task_id=payload.task_id,
        skill_name=payload.skill_name,
        question_count=payload.question_count,
        gateway=build_agent_gateway(get_settings(), db=db, owner_id=current_user.id),
    )


@router.get("/exams/{exam_id}")
def exam_detail(
    exam_id: str,
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return get_learning_exam_detail(db, student_id=current_user.id, exam_id=exam_id)


@router.post("/exams/{exam_id}/start")
def start_exam(
    exam_id: str,
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return start_learning_exam(db, student_id=current_user.id, exam_id=exam_id)


@router.post("/questions/{question_id}/favorite")
def favorite_question(
    question_id: str,
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return toggle_question_favorite(db, student_id=current_user.id, question_id=question_id)


@router.post("/exams/{exam_id}/submit")
def submit_exam(
    exam_id: str,
    payload: LearningExamSubmit,
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return submit_learning_exam(
        db,
        student_id=current_user.id,
        exam_id=exam_id,
        answers=payload.answers,
    )


@router.patch("/tasks/{task_id}")
def patch_task(
    task_id: str,
    payload: LearningTaskUpdate,
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return serialize_task(
        update_learning_task(
            db,
            student_id=current_user.id,
            task_id=task_id,
            status=payload.status,
            completion_note=payload.completion_note,
            evidence_url=payload.evidence_url,
        )
    )
