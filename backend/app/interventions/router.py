from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.models import User, UserRole
from app.auth.security import require_roles
from app.core.database import get_db
from app.core.errors import AppError
from app.interventions.models import Intervention
from app.students.service import assert_counselor_can_access_student


router = APIRouter(prefix="/interventions", tags=["interventions"])


class InterventionCreate(BaseModel):
    student_id: str
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=2000)


class FeedbackCreate(BaseModel):
    feedback: str = Field(min_length=1, max_length=2000)


def serialize(item: Intervention) -> dict[str, object]:
    return {
        "id": item.id,
        "student_id": item.student_id,
        "counselor_id": item.counselor_id,
        "title": item.title,
        "description": item.description,
        "status": item.status,
        "feedback": item.feedback,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_intervention(
    payload: InterventionCreate,
    current_user: User = Depends(require_roles(UserRole.counselor, UserRole.admin)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    assert_counselor_can_access_student(db, current_user, payload.student_id)
    item = Intervention(
        counselor_id=current_user.id,
        student_id=payload.student_id,
        title=payload.title,
        description=payload.description,
        status="assigned",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return serialize(item)


@router.patch("/{intervention_id}/submit")
def submit_intervention(
    intervention_id: str,
    payload: FeedbackCreate,
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = db.get(Intervention, intervention_id)
    if item is None or item.student_id != current_user.id:
        raise AppError(404, "intervention_not_found", "帮扶任务不存在")
    if item.status not in {"assigned", "acknowledged"}:
        raise AppError(409, "invalid_intervention_state", "帮扶任务当前不能提交")
    item.feedback = payload.feedback
    item.status = "submitted"
    db.commit()
    db.refresh(item)
    return serialize(item)


@router.patch("/{intervention_id}/resolve")
def resolve_intervention(
    intervention_id: str,
    current_user: User = Depends(require_roles(UserRole.counselor, UserRole.admin)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = db.get(Intervention, intervention_id)
    if item is None:
        raise AppError(404, "intervention_not_found", "帮扶任务不存在")
    assert_counselor_can_access_student(db, current_user, item.student_id)
    if item.status != "submitted":
        raise AppError(409, "invalid_intervention_state", "学生尚未提交任务反馈")
    item.status = "resolved"
    db.commit()
    db.refresh(item)
    return serialize(item)

