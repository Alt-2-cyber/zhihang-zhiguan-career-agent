import json
from collections.abc import Mapping

from sqlalchemy.orm import Session

from app.audit.models import AuditLog


def write_audit_log(
    db: Session,
    *,
    action: str,
    user_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: Mapping[str, object] | None = None,
) -> AuditLog:
    log = AuditLog(
        action=action,
        user_id=user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        details=json.dumps(details, ensure_ascii=False) if details else None,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log
