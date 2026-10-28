import asyncio
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Header, Query, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.ai.models import AITask, AITaskStatus, AITaskType, MediaArtifact
from app.ai.service import enqueue_task, ensure_task_available, utc_now
from app.auth.models import User
from app.auth.security import get_current_user
from app.chat.actions import confirm_action, reject_action, undo_action
from app.chat.attachments import create_chat_attachment
from app.chat.events import append_event, list_events
from app.chat.models import AgentRun, ChatMessage, ChatSession
from app.chat.run_details import serialize_run_details
from app.chat.schemas import (
    AgentRunDetails,
    ChatMessageAccepted,
    ChatMessageCreate,
    ChatSessionCreate,
    ChatSessionUpdate,
)
from app.chat.service import (
    assert_active_session,
    assert_session_access,
    create_chat_session,
    list_chat_sessions,
    serialize_message,
    serialize_session,
    update_chat_session,
    validate_context_refs,
    validate_message_attachments,
)
from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import AppError
from app.resumes.storage import build_storage
from app.tools.business import build_business_tool_registry

router = APIRouter(prefix="/chat", tags=["chat"])
TERMINAL_RUN_STATES = {"completed", "failed", "cancelled"}
ACTIVE_RUN_STATES = {"queued", "running"}


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
def create_session(
    payload: ChatSessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return serialize_session(create_chat_session(db, user=current_user, payload=payload))


@router.get("/sessions")
def list_sessions(
    query: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=30, ge=1, le=100),
    cursor_updated_at: datetime | None = None,
    cursor_id: str | None = Query(default=None, max_length=36),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    items, next_cursor = list_chat_sessions(
        db,
        user=current_user,
        query=query,
        limit=limit,
        cursor_updated_at=cursor_updated_at,
        cursor_id=cursor_id,
    )
    return {"items": [serialize_session(item) for item in items], "next_cursor": next_cursor}


@router.get("/sessions/{session_id}")
def read_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    chat_session = assert_session_access(db, current_user, session_id)
    active_run = _find_active_run(db, chat_session.id)
    if active_run is not None and _expire_stale_active_run(
        db,
        active_run,
        get_settings().agent_run_timeout_seconds,
    ):
        db.commit()
        active_run = None
    messages = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.session_id == chat_session.id)
        .order_by(ChatMessage.created_at, ChatMessage.id)
    ).all()
    return {
        **serialize_session(chat_session),
        "messages": [serialize_message(item) for item in messages],
        "active_run": _serialize_active_run(active_run),
    }


@router.patch("/sessions/{session_id}")
def update_session(
    session_id: str,
    payload: ChatSessionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    chat_session = assert_session_access(db, current_user, session_id)
    return serialize_session(
        update_chat_session(db, user=current_user, chat_session=chat_session, payload=payload)
    )


def _accepted(run: AgentRun) -> ChatMessageAccepted:
    return ChatMessageAccepted(
        message_id=run.user_message_id,
        run_id=run.id,
        events_url=f"/chat/runs/{run.id}/events",
    )


def _as_utc(value: datetime) -> datetime:
    return (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )


def _run_events_url(run: AgentRun) -> str:
    return f"/chat/runs/{run.id}/events"


def _serialize_active_run(run: AgentRun | None) -> dict[str, object] | None:
    if run is None or run.status not in ACTIVE_RUN_STATES:
        return None
    return {
        "run_id": run.id,
        "status": run.status,
        "events_url": _run_events_url(run),
        "user_message_id": run.user_message_id,
        "error_code": run.error_code,
        "created_at": run.created_at,
        "started_at": run.started_at,
    }


def _find_active_run(db: Session, session_id: str) -> AgentRun | None:
    return db.scalar(
        select(AgentRun).where(
            AgentRun.session_id == session_id,
            AgentRun.status.in_(ACTIVE_RUN_STATES),
        )
    )


def _expire_stale_active_run(db: Session, run: AgentRun, timeout_seconds: int) -> bool:
    if run.status not in ACTIVE_RUN_STATES:
        return False
    current = utc_now()
    anchor = run.started_at or run.created_at
    if current - _as_utc(anchor) <= timedelta(seconds=timeout_seconds):
        return False
    if _has_live_chat_agent_task(db, run, current):
        return False
    run.status = "failed"
    run.error_code = "agent_run_stale"
    run.error_message = "Agent 任务超过等待时间未完成，系统已释放会话，可重新发送。"
    run.completed_at = current
    append_event(
        db,
        run.id,
        "run.failed",
        {
            "error_code": run.error_code,
            "message": run.error_message,
        },
    )
    return True


def _has_live_chat_agent_task(db: Session, run: AgentRun, current: datetime) -> bool:
    task = db.scalar(
        select(AITask)
        .where(
            AITask.task_type == AITaskType.chat_agent_run,
            AITask.input_json.contains(run.id),
            AITask.status.in_([AITaskStatus.queued, AITaskStatus.running]),
        )
        .order_by(AITask.created_at.desc())
        .limit(1)
    )
    if task is None:
        return False
    if task.status == AITaskStatus.running:
        return task.lease_expires_at is None or _as_utc(task.lease_expires_at) > current
    if task.status == AITaskStatus.queued and task.available_at is not None:
        return _as_utc(task.available_at) > current
    return False


@router.post(
    "/sessions/{session_id}/messages",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ChatMessageAccepted,
)
def create_message(
    session_id: str,
    payload: ChatMessageCreate,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=120),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatMessageAccepted:
    chat_session = assert_session_access(db, current_user, session_id)
    db.scalar(select(ChatSession.id).where(ChatSession.id == session_id).with_for_update())
    assert_active_session(chat_session)
    existing_message = db.scalar(
        select(ChatMessage).where(
            ChatMessage.session_id == session_id,
            ChatMessage.request_key == idempotency_key,
        )
    )
    if existing_message is not None:
        existing_run = db.scalar(
            select(AgentRun).where(AgentRun.user_message_id == existing_message.id)
        )
        if existing_run is None:
            raise AppError(409, "agent_run_context_invalid", "消息执行状态不完整")
        return _accepted(existing_run)
    active_run = _find_active_run(db, session_id)
    if active_run is not None and not _expire_stale_active_run(
        db,
        active_run,
        get_settings().agent_run_timeout_seconds,
    ):
        raise AppError(409, "chat_run_active", "当前会话已有消息正在处理")
    validate_context_refs(
        db,
        user=current_user,
        chat_session=chat_session,
        refs=payload.context_refs,
    )
    validate_message_attachments(
        db,
        user=current_user,
        chat_session=chat_session,
        attachment_ids=payload.attachment_ids,
    )
    message = ChatMessage(
        session_id=chat_session.id,
        sender="user",
        content=payload.content,
        attachment_ids_json=json.dumps(payload.attachment_ids),
        citations_json=json.dumps(
            [item.model_dump(mode="json") for item in payload.context_refs],
            ensure_ascii=False,
        ),
        request_key=idempotency_key,
    )
    db.add(message)
    db.flush()
    run = AgentRun(
        session_id=chat_session.id,
        user_message_id=message.id,
        status="queued",
        plan_json="{}",
        provider="pending",
    )
    db.add(run)
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise AppError(409, "chat_run_active", "当前会话已有消息正在处理") from error
    append_event(db, run.id, "run.queued", {"message_id": message.id})
    enqueue_task(
        db,
        task_type=AITaskType.chat_agent_run,
        owner_id=current_user.id,
        input_data={"run_id": run.id},
    )
    db.commit()
    return _accepted(run)


def _assert_run_access(db: Session, user: User, run_id: str) -> AgentRun:
    run = db.get(AgentRun, run_id)
    chat_session = db.get(ChatSession, run.session_id) if run else None
    if run is None or chat_session is None or chat_session.owner_id != user.id:
        raise AppError(404, "agent_run_not_found", "Agent 执行记录不存在")
    assert_session_access(db, user, chat_session.id)
    return run


@router.get("/runs/{run_id}/details", response_model=AgentRunDetails)
def read_run_details(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AgentRunDetails:
    return serialize_run_details(db, _assert_run_access(db, current_user, run_id))


@router.get("/runs/{run_id}/events", response_class=StreamingResponse)
def stream_run_events(
    request: Request,
    run_id: str,
    after: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    _assert_run_access(db, current_user, run_id)
    session_factory = sessionmaker(bind=db.get_bind(), autoflush=False, expire_on_commit=False)
    timeout_seconds = get_settings().agent_run_timeout_seconds

    async def event_stream():
        cursor = after
        while True:
            with session_factory() as event_db:
                events = list_events(event_db, run_id, after_sequence=cursor)
                run = event_db.get(AgentRun, run_id)
                if run is not None and _expire_stale_active_run(
                    event_db,
                    run,
                    timeout_seconds,
                ):
                    event_db.commit()
                    events = list_events(event_db, run_id, after_sequence=cursor)
                    run = event_db.get(AgentRun, run_id)
                terminal = run is None or run.status in TERMINAL_RUN_STATES
            for event in events:
                cursor = event.sequence
                yield (
                    f"id: {event.sequence}\n"
                    f"event: {event.event_type}\n"
                    f"data: {event.payload_json}\n\n"
                )
            if terminal:
                return
            if await request.is_disconnected():
                return
            if not events:
                yield ": heartbeat\n\n"
            await asyncio.sleep(0.25)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/runs/{run_id}/retry", status_code=status.HTTP_202_ACCEPTED)
def retry_run(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    run = _assert_run_access(db, current_user, run_id)
    if run.status not in {"failed", "cancelled"}:
        raise AppError(409, "agent_run_not_retryable", "当前 Agent 执行不能重试")
    run.status = "queued"
    run.error_code = None
    run.error_message = None
    run.completed_at = None
    append_event(db, run.id, "run.queued", {"retry": True})
    enqueue_task(
        db,
        task_type=AITaskType.chat_agent_run,
        owner_id=current_user.id,
        input_data={"run_id": run.id},
    )
    db.commit()
    return {"run_id": run.id, "status": run.status}


@router.post("/actions/{proposal_id}/confirm")
def confirm_proposal(
    proposal_id: str,
    _idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=120),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return confirm_action(
        db,
        registry=build_business_tool_registry(),
        user=current_user,
        proposal_id=proposal_id,
    ).model_dump(mode="json")


@router.post("/actions/{proposal_id}/reject")
def reject_proposal(
    proposal_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return reject_action(db, user=current_user, proposal_id=proposal_id).model_dump(mode="json")


@router.post("/actions/{proposal_id}/undo")
def undo_proposal(
    proposal_id: str,
    _idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=120),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return undo_action(
        db,
        registry=build_business_tool_registry(),
        user=current_user,
        proposal_id=proposal_id,
    ).model_dump(mode="json")


@router.post("/sessions/{session_id}/transcriptions", status_code=status.HTTP_202_ACCEPTED)
def upload_chat_recording(
    session_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    chat_session = assert_session_access(db, current_user, session_id)
    assert_active_session(chat_session)
    ensure_task_available(AITaskType.chat_transcription)
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
        f"media/chat-recordings/{uuid4().hex}{suffixes[media_type]}",
        content,
        media_type=media_type,
    )
    artifact = MediaArtifact(
        owner_id=current_user.id,
        chat_session_id=chat_session.id,
        kind="chat_recording",
        media_type=media_type,
        storage_path=storage_ref,
        size_bytes=len(content),
        expires_at=utc_now() + timedelta(days=settings.audio_retention_days),
    )
    db.add(artifact)
    db.flush()
    task = enqueue_task(
        db,
        task_type=AITaskType.chat_transcription,
        owner_id=current_user.id,
        input_data={
            "storage_ref": storage_ref,
            "media_type": media_type,
            "chat_session_id": chat_session.id,
            "artifact_id": artifact.id,
        },
    )
    db.commit()
    return {"task_id": task.id, "artifact_id": artifact.id, "status": task.status}


@router.post("/sessions/{session_id}/attachments", status_code=status.HTTP_202_ACCEPTED)
def upload_chat_attachment(
    session_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    chat_session = assert_session_access(db, current_user, session_id)
    assert_active_session(chat_session)
    settings = get_settings()
    content = file.file.read(settings.max_upload_size_mb * 1024 * 1024 + 1)
    attachment, task_id = create_chat_attachment(
        db,
        user=current_user,
        chat_session=chat_session,
        filename=file.filename or "attachment",
        media_type=file.content_type or "application/octet-stream",
        content=content,
        settings=settings,
    )
    db.commit()
    return {
        "id": attachment.id,
        "task_id": task_id,
        "parse_status": attachment.parse_status,
        "original_name": attachment.original_name,
    }


@router.post("/messages/{message_id}/synthesis", status_code=status.HTTP_202_ACCEPTED)
def synthesize_chat_message(
    message_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    message = db.get(ChatMessage, message_id)
    chat_session = db.get(ChatSession, message.session_id) if message else None
    if (
        message is None
        or message.sender != "assistant"
        or chat_session is None
        or chat_session.owner_id != current_user.id
    ):
        raise AppError(404, "chat_message_not_found", "Agent 回复不存在")
    task = enqueue_task(
        db,
        task_type=AITaskType.chat_synthesis,
        owner_id=current_user.id,
        input_data={"text": message.content, "chat_session_id": chat_session.id},
    )
    db.commit()
    return {"task_id": task.id, "status": task.status}
