import httpx
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.models import User, UserRole
from app.auth.security import require_roles
from app.core.config import get_settings
from app.core.database import get_db
from app.intelligence.service import job_intelligence_overview, refresh_job_sources

router = APIRouter(prefix="/intelligence", tags=["intelligence"])


@router.get("/overview")
def overview(
    _user: User = Depends(require_roles(UserRole.student, UserRole.counselor, UserRole.admin)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return job_intelligence_overview(db)


@router.post("/sources/refresh")
def refresh_sources(
    force: bool = False,
    _user: User = Depends(require_roles(UserRole.student, UserRole.counselor, UserRole.admin)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    settings = get_settings()
    with httpx.Client(timeout=settings.public_job_search_timeout_seconds) as client:
        summary = refresh_job_sources(
            db,
            client=client,
            force=force,
            retry_attempts=settings.public_job_search_retry_attempts,
        )
    db.commit()
    return summary
