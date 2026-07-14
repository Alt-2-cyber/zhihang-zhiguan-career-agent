import json

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.applications.models import Application
from app.auth.models import User, UserRole
from app.auth.security import require_roles
from app.core.database import get_db
from app.risks.models import RiskEvent


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


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
        db.scalar(select(func.count()).select_from(Application).where(Application.student_id.in_(student_ids)))
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
    }

