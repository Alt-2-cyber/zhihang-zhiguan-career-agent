from sqlalchemy.orm import Session

from app.applications.models import Application, ApplicationEvent
from app.auth.models import User
from app.core.errors import AppError

ALLOWED_TRANSITIONS = {
    "saved": {"applied", "closed"},
    "applied": {"assessment", "interview", "closed"},
    "assessment": {"interview", "closed"},
    "interview": {"offered", "closed"},
    "offered": {"closed"},
    "closed": set(),
}


def transition_application_stage(
    db: Session, *, student: User, application_id: str, stage: str
) -> tuple[Application, str]:
    application = db.get(Application, application_id)
    if application is None or application.student_id != student.id:
        raise AppError(404, "application_not_found", "投递记录不存在")
    if stage not in ALLOWED_TRANSITIONS.get(application.stage, set()):
        raise AppError(409, "invalid_stage_transition", "投递阶段不能执行该变化")
    previous = application.stage
    application.stage = stage
    db.add(
        ApplicationEvent(
            application_id=application.id,
            student_id=student.id,
            from_stage=previous,
            to_stage=stage,
        )
    )
    return application, previous
