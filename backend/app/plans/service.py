import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.base import AgentGateway
from app.auth.models import User
from app.core.errors import AppError
from app.plans.models import CareerPlanRecord, PlanTaskRecord
from app.students.service import get_student_profile


def generate_plan(
    db: Session, *, student: User, target_role: str | None, gateway: AgentGateway
) -> CareerPlanRecord:
    profile = get_student_profile(db, student.id)
    generated = gateway.build_plan(profile.summary, target_role)
    plan = CareerPlanRecord(
        student_id=student.id,
        provider=generated.provider,
        primary_role=generated.primary_role,
        backup_roles_json=json.dumps(generated.backup_roles, ensure_ascii=False),
        rationale=generated.rationale,
        status="pending_confirmation",
    )
    db.add(plan)
    db.flush()
    for task in generated.tasks:
        db.add(
            PlanTaskRecord(
                plan_id=plan.id,
                student_id=student.id,
                title=task.title,
                week=task.week,
                due_date=task.due_date,
                acceptance_criteria=task.acceptance_criteria,
                status="pending",
            )
        )
    db.commit()
    db.refresh(plan)
    return plan


def confirm_plan(db: Session, *, student: User, plan_id: str) -> CareerPlanRecord:
    plan = db.get(CareerPlanRecord, plan_id)
    if plan is None or plan.student_id != student.id:
        raise AppError(404, "plan_not_found", "求职计划不存在")
    if plan.status != "pending_confirmation":
        raise AppError(409, "plan_already_confirmed", "求职计划已经确认")
    plan.status = "active"
    db.commit()
    db.refresh(plan)
    return plan


def serialize_plan(db: Session, plan: CareerPlanRecord) -> dict[str, object]:
    tasks = db.scalars(
        select(PlanTaskRecord)
        .where(PlanTaskRecord.plan_id == plan.id)
        .order_by(PlanTaskRecord.week)
    ).all()
    return {
        "id": plan.id,
        "provider": plan.provider,
        "primary_role": plan.primary_role,
        "backup_roles": json.loads(plan.backup_roles_json),
        "rationale": plan.rationale,
        "status": plan.status,
        "tasks": [
            {
                "id": task.id,
                "title": task.title,
                "week": task.week,
                "due_date": task.due_date,
                "acceptance_criteria": task.acceptance_criteria,
                "status": task.status,
            }
            for task in tasks
        ],
    }

