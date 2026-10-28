import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.contracts import WeeklyMetrics
from app.agents.service import build_agent_gateway
from app.applications.models import ApplicationEvent
from app.auth.models import User, UserRole
from app.auth.security import require_roles
from app.core.config import get_settings
from app.core.database import get_db
from app.reviews.models import WeeklyReviewRecord

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.post("/weekly", status_code=status.HTTP_201_CREATED)
def create_weekly_review(
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    since = datetime.now(timezone.utc) - timedelta(days=7)
    events = db.scalars(
        select(ApplicationEvent).where(
            ApplicationEvent.student_id == current_user.id,
            ApplicationEvent.occurred_at >= since,
        )
    ).all()
    stage_counts = {
        stage: sum(1 for event in events if event.to_stage == stage)
        for stage in ("applied", "assessment", "interview", "offered")
    }
    metrics = WeeklyMetrics(
        applications=stage_counts["applied"],
        responses=sum(stage_counts.values()) - stage_counts["applied"],
        assessments=stage_counts["assessment"],
        interviews=stage_counts["interview"],
        offers=stage_counts["offered"],
    )
    result = build_agent_gateway(get_settings(), db=db, owner_id=current_user.id).build_weekly_review(metrics)
    record = WeeklyReviewRecord(
        student_id=current_user.id,
        provider=result.provider,
        metrics_json=result.metrics.model_dump_json(),
        insights_json=json.dumps(result.insights, ensure_ascii=False),
        actions_json=json.dumps(result.actions, ensure_ascii=False),
        status="pending_confirmation",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {
        "id": record.id,
        "provider": record.provider,
        "metrics": json.loads(record.metrics_json),
        "insights": json.loads(record.insights_json),
        "actions": json.loads(record.actions_json),
        "status": record.status,
    }
