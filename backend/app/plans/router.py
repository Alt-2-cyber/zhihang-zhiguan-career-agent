from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.service import build_agent_gateway
from app.auth.models import User, UserRole
from app.auth.security import require_roles
from app.core.config import get_settings
from app.core.database import get_db
from app.plans.models import CareerPlanRecord
from app.plans.schemas import CareerPlanRead, PlanGenerateRequest
from app.plans.service import confirm_plan, generate_plan, serialize_plan

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("/current", response_model=CareerPlanRead)
def read_current_plan(
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    from app.core.errors import AppError

    plan = db.scalar(
        select(CareerPlanRecord)
        .where(CareerPlanRecord.student_id == current_user.id)
        .order_by(CareerPlanRecord.created_at.desc())
    )
    if plan is None:
        raise AppError(404, "plan_not_found", "尚未生成求职计划")
    return serialize_plan(db, plan)


@router.post("/generate", response_model=CareerPlanRead, status_code=status.HTTP_201_CREATED)
def create_generated_plan(
    payload: PlanGenerateRequest,
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    plan = generate_plan(
        db,
        student=current_user,
        target_role=payload.target_role,
        gateway=build_agent_gateway(get_settings(), db=db, owner_id=current_user.id),
    )
    return serialize_plan(db, plan)


@router.post("/{plan_id}/confirm", response_model=CareerPlanRead)
def confirm_generated_plan(
    plan_id: str,
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return serialize_plan(db, confirm_plan(db, student=current_user, plan_id=plan_id))
