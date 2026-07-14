from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.applications.models import Application, ApplicationEvent
from app.auth.models import User, UserRole
from app.auth.security import require_roles
from app.core.database import get_db
from app.core.errors import AppError
from app.jobs.models import Job


router = APIRouter(prefix="/applications", tags=["applications"])

ALLOWED_TRANSITIONS = {
    "saved": {"applied", "closed"},
    "applied": {"assessment", "interview", "closed"},
    "assessment": {"interview", "closed"},
    "interview": {"offered", "closed"},
    "offered": {"closed"},
    "closed": set(),
}


class ApplicationCreate(BaseModel):
    job_id: str
    resume_version_id: str | None = None


class StageUpdate(BaseModel):
    stage: str


def serialize(application: Application) -> dict[str, object]:
    return {
        "id": application.id,
        "job_id": application.job_id,
        "resume_version_id": application.resume_version_id,
        "stage": application.stage,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_application(
    payload: ApplicationCreate,
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    if db.get(Job, payload.job_id) is None:
        raise AppError(404, "job_not_found", "岗位不存在")
    application = Application(
        student_id=current_user.id,
        job_id=payload.job_id,
        resume_version_id=payload.resume_version_id,
        stage="saved",
    )
    db.add(application)
    db.flush()
    db.add(
        ApplicationEvent(
            application_id=application.id,
            student_id=current_user.id,
            from_stage=None,
            to_stage="saved",
        )
    )
    db.commit()
    db.refresh(application)
    return serialize(application)


@router.patch("/{application_id}/stage")
def update_application_stage(
    application_id: str,
    payload: StageUpdate,
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    application = db.get(Application, application_id)
    if application is None or application.student_id != current_user.id:
        raise AppError(404, "application_not_found", "投递记录不存在")
    if payload.stage not in ALLOWED_TRANSITIONS.get(application.stage, set()):
        raise AppError(409, "invalid_stage_transition", "投递阶段不能执行该变化")
    previous = application.stage
    application.stage = payload.stage
    db.add(
        ApplicationEvent(
            application_id=application.id,
            student_id=current_user.id,
            from_stage=previous,
            to_stage=payload.stage,
        )
    )
    db.commit()
    db.refresh(application)
    return serialize(application)

