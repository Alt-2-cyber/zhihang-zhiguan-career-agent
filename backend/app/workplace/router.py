from datetime import timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.service import build_agent_gateway
from app.ai.models import AITaskType, MediaArtifact
from app.ai.service import enqueue_task, utc_now
from app.auth.models import User, UserRole
from app.auth.security import require_roles
from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import AppError
from app.resumes.storage import build_storage
from app.workplace.models import SimulationScenario, SimulationSession
from app.workplace.service import (
    _get_owned_workplace_session,
    _serialize_deliverable,
    answer_session,
    bind_material,
    control_session,
    generate_workplace_deliverable,
    list_available_materials,
    list_training_reports,
    list_workplace_deliverables,
    save_workplace_deliverable,
    serialize_scenario,
    session_detail,
    start_session,
    submit_workplace_deliverable,
)

router = APIRouter(prefix="/workplace", tags=["workplace"])


class AnswerRequest(BaseModel):
    response: str = Field(min_length=20, max_length=8000)


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10_000)


class MaterialBindingRequest(BaseModel):
    source_type: str = Field(default="resume", max_length=30)
    source_id: str = Field(min_length=1, max_length=36)
    purpose: str = Field(default="answer_context", max_length=60)


class SessionControlRequest(BaseModel):
    action: str = Field(pattern="^(pause|resume|lower_pressure|set_pressure|stop|complete)$")
    pressure_level: str | None = Field(default=None, pattern="^(light|medium|high)$")


class WorkplaceDeliverableRequest(BaseModel):
    action_type: str = Field(min_length=1, max_length=40)
    title: str = Field(default="", max_length=200)
    content: str = Field(min_length=20, max_length=20_000)


class WorkplaceAssistRequest(BaseModel):
    action_type: str = Field(min_length=1, max_length=40)


@router.get("/scenarios")
def scenarios(
    phase: str | None = Query(default=None, pattern="^(pre_hire|post_hire)$"),
    _user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    query = select(SimulationScenario).where(SimulationScenario.status == "active")
    if phase == "post_hire":
        query = query.where(SimulationScenario.mode == "workplace")
    elif phase == "pre_hire":
        query = query.where(SimulationScenario.mode != "workplace")
    return [
        serialize_scenario(item)
        for item in db.scalars(query.order_by(SimulationScenario.difficulty, SimulationScenario.title)).all()
    ]


@router.get("/sessions")
def sessions(
    phase: str | None = Query(default=None, pattern="^(pre_hire|post_hire)$"),
    current_user: User = Depends(require_roles(UserRole.student)), db: Session = Depends(get_db)
) -> list[dict[str, object]]:
    query = select(SimulationSession).where(SimulationSession.student_id == current_user.id)
    if phase == "post_hire":
        query = query.where(SimulationSession.mode == "workplace")
    elif phase == "pre_hire":
        query = query.where(SimulationSession.mode != "workplace")
    return [
        session_detail(db, item)
        for item in db.scalars(query.order_by(SimulationSession.updated_at.desc()).limit(30)).all()
    ]


@router.get("/materials")
def materials(
    current_user: User = Depends(require_roles(UserRole.student)), db: Session = Depends(get_db)
) -> list[dict[str, object]]:
    return list_available_materials(db, student_id=current_user.id)


@router.get("/reports")
def reports(
    phase: str | None = Query(default=None, pattern="^(pre_hire|post_hire)$"),
    current_user: User = Depends(require_roles(UserRole.student)), db: Session = Depends(get_db)
) -> list[dict[str, object]]:
    return list_training_reports(db, student_id=current_user.id, phase=phase)


@router.post("/scenarios/{scenario_id}/sessions", status_code=status.HTTP_201_CREATED)
def create_session(
    scenario_id: str,
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return session_detail(db, start_session(db, current_user.id, scenario_id))


@router.post("/sessions/{session_id}/answers")
def answer(
    session_id: str,
    payload: AnswerRequest,
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return session_detail(
        db,
        answer_session(
            db,
            student_id=current_user.id,
            session_id=session_id,
            response=payload.response,
            gateway=build_agent_gateway(get_settings(), db=db, owner_id=current_user.id),
        ),
    )


@router.get("/sessions/{session_id}/brief")
def workplace_brief(
    session_id: str,
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    detail = session_detail(
        db, _get_owned_workplace_session(db, student_id=current_user.id, session_id=session_id)
    )
    return {
        "session_id": detail["id"],
        "scenario": detail["scenario"],
        "phase": detail["phase"],
        "work_context": detail["work_context"],
        "status": detail["status"],
        "deliverables": detail["deliverables"],
    }


@router.get("/sessions/{session_id}/deliverables")
def workplace_deliverables(
    session_id: str,
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    return list_workplace_deliverables(db, student_id=current_user.id, session_id=session_id)


@router.post("/sessions/{session_id}/deliverables")
def save_deliverable(
    session_id: str,
    payload: WorkplaceDeliverableRequest,
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = save_workplace_deliverable(
        db,
        student_id=current_user.id,
        session_id=session_id,
        action_type=payload.action_type,
        title=payload.title,
        content=payload.content,
    )
    return {"deliverable": _serialize_deliverable(item)}


@router.post("/sessions/{session_id}/deliverables/submit")
def submit_deliverable(
    session_id: str,
    payload: WorkplaceDeliverableRequest,
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item = submit_workplace_deliverable(
        db,
        student_id=current_user.id,
        session_id=session_id,
        action_type=payload.action_type,
        title=payload.title,
        content=payload.content,
    )
    return {"deliverable": _serialize_deliverable(item)}


@router.post("/sessions/{session_id}/workplace-assist")
def workplace_assist(
    session_id: str,
    payload: WorkplaceAssistRequest,
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    item, generated = generate_workplace_deliverable(
        db,
        student_id=current_user.id,
        session_id=session_id,
        action_type=payload.action_type,
        gateway=build_agent_gateway(get_settings(), db=db, owner_id=current_user.id),
    )
    return {
        "deliverable": _serialize_deliverable(item),
        "provider": getattr(generated, "provider", "unknown"),
        "rationale": getattr(generated, "rationale", []),
    }


@router.post("/sessions/{session_id}/recordings", status_code=status.HTTP_202_ACCEPTED)
def upload_training_recording(
    session_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    session = db.get(SimulationSession, session_id)
    if session is None or session.student_id != current_user.id:
        raise AppError(404, "simulation_session_not_found", "训练会话不存在")
    if session.status != "active":
        raise AppError(409, "simulation_session_not_active", "训练会话未处于进行中状态")
    media_type = file.content_type or "application/octet-stream"
    suffixes = {
        "audio/webm": ".webm",
        "audio/ogg": ".ogg",
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
    }
    if media_type not in suffixes:
        raise AppError(415, "unsupported_audio", "仅支持 WebM、Ogg 或 WAV 录音")
    settings = get_settings()
    max_bytes = settings.max_audio_size_mb * 1024 * 1024
    content = file.file.read(max_bytes + 1)
    if not content or len(content) > max_bytes:
        raise AppError(413, "audio_too_large", "录音为空或超过大小限制")
    storage_ref = build_storage(settings).put_bytes(
        f"media/workplace-recordings/{uuid4().hex}{suffixes[media_type]}",
        content,
        media_type=media_type,
    )
    artifact = MediaArtifact(
        owner_id=current_user.id,
        session_id=None,
        kind="workplace_recording",
        media_type=media_type,
        storage_path=storage_ref,
        size_bytes=len(content),
        expires_at=utc_now() + timedelta(days=settings.audio_retention_days),
    )
    db.add(artifact)
    db.flush()
    task = enqueue_task(
        db,
        task_type=AITaskType.speech_transcription,
        owner_id=current_user.id,
        input_data={
            "storage_ref": storage_ref,
            "media_type": media_type,
            "workplace_session_id": session.id,
            "artifact_id": artifact.id,
        },
    )
    db.commit()
    return {"task_id": task.id, "artifact_id": artifact.id, "status": task.status}


@router.post("/sessions/{session_id}/speech", status_code=status.HTTP_202_ACCEPTED)
def synthesize_training_prompt(
    session_id: str,
    payload: SpeechRequest,
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    session = db.get(SimulationSession, session_id)
    if session is None or session.student_id != current_user.id:
        raise AppError(404, "simulation_session_not_found", "训练会话不存在")
    if session.status != "active":
        raise AppError(409, "simulation_session_not_active", "训练会话未处于进行中状态")
    task = enqueue_task(
        db,
        task_type=AITaskType.speech_synthesis,
        owner_id=current_user.id,
        input_data={"text": payload.text.strip(), "workplace_session_id": session.id},
    )
    db.commit()
    return {"task_id": task.id, "status": task.status}


@router.post("/sessions/{session_id}/materials")
def bind_session_material(
    session_id: str,
    payload: MaterialBindingRequest,
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    binding = bind_material(
        db,
        student_id=current_user.id,
        session_id=session_id,
        source_type=payload.source_type,
        source_id=payload.source_id,
        purpose=payload.purpose,
    )
    return {"id": binding.id, "status": "bound"}


@router.post("/sessions/{session_id}/controls")
def control(
    session_id: str,
    payload: SessionControlRequest,
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    session = control_session(
        db,
        student_id=current_user.id,
        session_id=session_id,
        action=payload.action,
        pressure_level=payload.pressure_level,
    )
    return session_detail(db, session)
