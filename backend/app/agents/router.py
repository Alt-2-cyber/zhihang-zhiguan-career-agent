from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents.analytics import summarize_model_usage
from app.auth.models import User, UserRole
from app.auth.security import require_roles
from app.core.database import get_db

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/usage")
def model_usage_summary(
    days: int = 7,
    provider: str | None = None,
    operation: str | None = None,
    _current_user: User = Depends(require_roles(UserRole.counselor, UserRole.admin)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return summarize_model_usage(db, days=days, provider=provider, operation=operation)
