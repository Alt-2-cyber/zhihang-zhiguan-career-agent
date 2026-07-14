import json

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.applications.models import Application
from app.auth.models import User, UserRole
from app.auth.security import require_roles
from app.core.database import get_db
from app.plans.models import CareerPlanRecord, PlanTaskRecord
from app.risks.models import RiskEvent
from app.students.models import StudentProfile

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/student")
def student_dashboard(
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    applications = db.scalars(
        select(Application).where(Application.student_id == current_user.id)
    ).all()
    stage_counts: dict[str, int] = {}
    for item in applications:
        stage_counts[item.stage] = stage_counts.get(item.stage, 0) + 1
    active_plan = db.scalar(
        select(CareerPlanRecord)
        .where(CareerPlanRecord.student_id == current_user.id)
        .order_by(CareerPlanRecord.created_at.desc())
    )
    tasks = (
        db.scalars(
            select(PlanTaskRecord)
            .where(PlanTaskRecord.plan_id == active_plan.id)
            .order_by(PlanTaskRecord.due_date)
        ).all()
        if active_plan
        else []
    )
    risk_count = int(
        db.scalar(
            select(func.count())
            .select_from(RiskEvent)
            .where(RiskEvent.student_id == current_user.id, RiskEvent.status == "open")
        )
        or 0
    )
    profile_exists = (
        db.scalar(select(StudentProfile.id).where(StudentProfile.student_id == current_user.id))
        is not None
    )
    return {
        "profile_confirmed": profile_exists,
        "primary_role": active_plan.primary_role if active_plan else None,
        "application_count": len(applications),
        "stage_counts": stage_counts,
        "risk_count": risk_count,
        "tasks": [
            {
                "id": task.id,
                "title": task.title,
                "due_date": task.due_date.isoformat(),
                "status": task.status,
            }
            for task in tasks[:6]
        ],
    }


@router.get("/counselor")
def counselor_dashboard(
    current_user: User = Depends(require_roles(UserRole.counselor, UserRole.admin)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    student_ids = db.scalars(
        select(User.id).where(
            User.role == UserRole.student,
            User.class_id == current_user.class_id,
            User.is_active.is_(True),
        )
    ).all()
    risks = (
        db.scalars(
            select(RiskEvent).where(
                RiskEvent.student_id.in_(student_ids), RiskEvent.status == "open"
            )
        ).all()
        if student_ids
        else []
    )
    application_count = (
        db.scalar(
            select(func.count())
            .select_from(Application)
            .where(Application.student_id.in_(student_ids))
        )
        if student_ids
        else 0
    )
    return {
        "student_count": len(student_ids),
        "application_count": int(application_count or 0),
        "risk_count": len(risks),
        "risks": [
            {
                "id": item.id,
                "student_id": item.student_id,
                "rule_code": item.rule_code,
                "level": item.level,
                "facts": json.loads(item.facts_json),
            }
            for item in risks
        ],
        "students": [
            {
                "id": student.id,
                "display_name": student.display_name,
                "username": student.username,
                "risk_count": sum(1 for item in risks if item.student_id == student.id),
            }
            for student in db.scalars(select(User).where(User.id.in_(student_ids))).all()
        ]
        if student_ids
        else [],
    }
