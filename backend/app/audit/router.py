import csv
import io
import json
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.models import AuditLog
from app.auth.models import User, UserRole
from app.auth.security import require_roles
from app.core.database import get_db

router = APIRouter(prefix="/audit", tags=["audit"])


def _details(raw: str | None) -> dict[str, object] | None:
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": "[unparseable]"}
    return value if isinstance(value, dict) else {"value": value}


def _serialize(log: AuditLog) -> dict[str, object]:
    return {
        "id": log.id,
        "user_id": log.user_id,
        "action": log.action,
        "resource_type": log.resource_type,
        "resource_id": log.resource_id,
        "details": _details(log.details),
        "created_at": log.created_at,
    }


def _query_logs(
    db: Session,
    *,
    action: str | None,
    user_id: str | None,
    created_from: datetime | None,
    created_to: datetime | None,
    limit: int,
) -> list[AuditLog]:
    statement = select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
    if action:
        statement = statement.where(AuditLog.action == action)
    if user_id:
        statement = statement.where(AuditLog.user_id == user_id)
    if created_from:
        statement = statement.where(AuditLog.created_at >= created_from)
    if created_to:
        statement = statement.where(AuditLog.created_at <= created_to)
    return list(db.scalars(statement.limit(limit)).all())


@router.get("/logs")
def list_audit_logs(
    action: str | None = Query(default=None, max_length=100),
    user_id: str | None = Query(default=None, max_length=36),
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=1_000),
    _current_user: User = Depends(require_roles(UserRole.counselor, UserRole.admin)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    logs = _query_logs(
        db,
        action=action,
        user_id=user_id,
        created_from=created_from,
        created_to=created_to,
        limit=limit,
    )
    return {"items": [_serialize(log) for log in logs], "count": len(logs)}


@router.get("/logs/export.csv")
def export_audit_logs_csv(
    action: str | None = Query(default=None, max_length=100),
    user_id: str | None = Query(default=None, max_length=36),
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    limit: int = Query(default=1_000, ge=1, le=5_000),
    _current_user: User = Depends(require_roles(UserRole.counselor, UserRole.admin)),
    db: Session = Depends(get_db),
) -> Response:
    logs = _query_logs(
        db,
        action=action,
        user_id=user_id,
        created_from=created_from,
        created_to=created_to,
        limit=limit,
    )
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "id",
            "created_at",
            "user_id",
            "action",
            "resource_type",
            "resource_id",
            "details",
        ],
    )
    writer.writeheader()
    for log in logs:
        writer.writerow(
            {
                "id": log.id,
                "created_at": log.created_at.isoformat(),
                "user_id": log.user_id or "",
                "action": log.action,
                "resource_type": log.resource_type or "",
                "resource_id": log.resource_id or "",
                "details": json.dumps(_details(log.details) or {}, ensure_ascii=False),
            }
        )
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="audit-logs.csv"'},
    )
