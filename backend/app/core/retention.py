from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.agents.models import AgentModelCall
from app.ai.models import AITask, AITaskStatus
from app.audit.models import AuditLog


def cleanup_retained_data(
    db: Session,
    *,
    audit_days: int,
    usage_days: int,
    task_days: int,
    now: datetime | None = None,
) -> dict[str, int]:
    current = now or datetime.now(timezone.utc)
    audit_cutoff = current - timedelta(days=audit_days)
    usage_cutoff = current - timedelta(days=usage_days)
    task_cutoff = current - timedelta(days=task_days)
    audit_result = db.execute(delete(AuditLog).where(AuditLog.created_at < audit_cutoff))
    usage_result = db.execute(
        delete(AgentModelCall).where(AgentModelCall.completed_at < usage_cutoff)
    )
    task_result = db.execute(
        delete(AITask).where(
            AITask.completed_at < task_cutoff,
            AITask.status.in_([AITaskStatus.succeeded, AITaskStatus.cancelled]),
            AITask.dead_lettered_at.is_(None),
        )
    )
    db.flush()
    return {
        "audit_logs": int(audit_result.rowcount or 0),
        "model_calls": int(usage_result.rowcount or 0),
        "completed_tasks": int(task_result.rowcount or 0),
    }


def cleanup_retained_data_job() -> None:
    from app.core.config import get_settings
    from app.core.database import SessionLocal

    settings = get_settings()
    with SessionLocal() as db:
        cleanup_retained_data(
            db,
            audit_days=settings.audit_retention_days,
            usage_days=settings.agent_usage_retention_days,
            task_days=settings.completed_task_retention_days,
        )
        db.commit()
