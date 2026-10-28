import hashlib
import json
import signal
import time
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from types import FrameType
from uuid import uuid4

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.agents.base import AgentGateway
from app.agents.conversation_gateway import ConversationGateway
from app.agents.service import build_agent_gateway, build_conversation_gateway
from app.ai.clients import AIServiceError, LocalAIClients
from app.ai.models import AITask, AITaskStatus, AITaskType, DocumentChunk, MediaArtifact
from app.ai.service import claim_next_task, complete_task, enqueue_task, fail_task, utc_now
from app.auth.models import User, UserRole
from app.chat.models import ChatAttachment
from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.jobs.models import Job
from app.jobs.retrieval import chunk_text
from app.resumes.models import ResumeFile
from app.resumes.storage import build_storage
from app.students.service import create_profile_analysis, serialize_profile_analysis_draft
from app.tools.business import build_business_tool_registry
from app.tools.registry import ToolRegistry


def _resume_ocr(
    db: Session, task: AITask, clients: LocalAIClients, settings: Settings
) -> dict[str, object]:
    resume_id = str(task.input_data.get("resume_id", ""))
    resume = db.get(ResumeFile, resume_id)
    if resume is None or resume.student_id != task.owner_id:
        raise AIServiceError("resume_not_found", "resume is unavailable")
    storage = build_storage(settings)
    with storage.materialize(resume.storage_path, suffix=".pdf") as path:
        result = clients.ocr(path)
    if not result.text.strip():
        raise AIServiceError("ocr_empty", "ocr returned no readable text")
    resume.parsed_text = result.text.strip()
    resume.parse_status = "embedding"
    resume.parse_error = None
    embedding_task = enqueue_task(
        db,
        task_type=AITaskType.document_embedding,
        owner_id=task.owner_id,
        input_data={"source_type": "resume", "source_id": resume.id},
    )
    return {"page_count": len(result.pages), "embedding_task_id": embedding_task.id}


def _profile_analysis(
    db: Session,
    task: AITask,
    gateway: AgentGateway,
) -> dict[str, object]:
    student = db.get(User, task.owner_id)
    resume_text = task.input_data.get("resume_text")
    preferences = task.input_data.get("preferences")
    if (
        student is None
        or student.role != UserRole.student
        or not isinstance(resume_text, str)
        or not resume_text.strip()
        or not isinstance(preferences, dict)
    ):
        raise AIServiceError("profile_input_invalid", "profile input is unavailable")
    draft = create_profile_analysis(
        db,
        student=student,
        resume_text=resume_text,
        preferences={str(key): str(value) for key, value in preferences.items()},
        gateway=gateway,
    )
    return serialize_profile_analysis_draft(draft)


def _source_content(db: Session, task: AITask) -> tuple[str, str | None, str]:
    source_type = str(task.input_data.get("source_type", ""))
    source_id = str(task.input_data.get("source_id", ""))
    if source_type == "resume":
        resume = db.get(ResumeFile, source_id)
        if resume is None or resume.student_id != task.owner_id or not resume.parsed_text:
            raise AIServiceError("resume_not_ready", "resume text is unavailable")
        return resume.parsed_text, resume.student_id, source_type
    if source_type == "job":
        job = db.get(Job, source_id)
        if job is None:
            raise AIServiceError("job_not_found", "job text is unavailable")
        text = f"{job.title}\n{job.company}\n{job.location}\n{job.description}"
        return text, None, source_type
    raise AIServiceError("unsupported_source", "document source is unsupported")


def _document_embedding(db: Session, task: AITask, clients: LocalAIClients) -> dict[str, object]:
    source_id = str(task.input_data.get("source_id", ""))
    content, owner_id, source_type = _source_content(db, task)
    chunks = chunk_text(content)
    if not chunks:
        raise AIServiceError("empty_document", "document contains no indexable text")
    embedding = clients.embed(chunks)
    db.execute(
        delete(DocumentChunk).where(
            DocumentChunk.source_type == source_type,
            DocumentChunk.source_id == source_id,
        )
    )
    for index, (chunk, vector) in enumerate(zip(chunks, embedding.vectors, strict=True)):
        db.add(
            DocumentChunk(
                source_type=source_type,
                source_id=source_id,
                owner_id=owner_id,
                chunk_index=index,
                content=chunk,
                content_hash=hashlib.sha256(chunk.encode("utf-8")).hexdigest(),
                embedding=vector,
                metadata_json=json.dumps({"model": embedding.model}),
            )
        )
    if source_type == "resume":
        resume = db.get(ResumeFile, source_id)
        assert resume is not None
        resume.parse_status = "parsed"
        resume.parse_error = None
    db.flush()
    return {"chunk_count": len(chunks), "model": embedding.model}


def _chat_attachment_ocr(
    db: Session, task: AITask, clients: LocalAIClients, settings: Settings
) -> dict[str, object]:
    attachment_id = str(task.input_data.get("attachment_id", ""))
    attachment = db.get(ChatAttachment, attachment_id)
    if attachment is None or attachment.owner_id != task.owner_id:
        raise AIServiceError("chat_attachment_not_found", "chat attachment is unavailable")
    storage = build_storage(settings)
    with storage.materialize(attachment.storage_path, suffix=".pdf") as path:
        result = clients.ocr(path)
    if not result.text.strip():
        raise AIServiceError("ocr_empty", "ocr returned no readable text")
    attachment.parsed_text = result.text.strip()
    attachment.parse_status = "embedding"
    attachment.parse_error = None
    embedding_task = enqueue_task(
        db,
        task_type=AITaskType.chat_attachment_embedding,
        owner_id=task.owner_id,
        input_data={"attachment_id": attachment.id},
    )
    attachment.ai_task_id = embedding_task.id
    return {"page_count": len(result.pages), "embedding_task_id": embedding_task.id}


def _chat_attachment_embedding(
    db: Session, task: AITask, clients: LocalAIClients
) -> dict[str, object]:
    attachment_id = str(task.input_data.get("attachment_id", ""))
    attachment = db.get(ChatAttachment, attachment_id)
    if attachment is None or attachment.owner_id != task.owner_id or not attachment.parsed_text:
        raise AIServiceError("chat_attachment_not_ready", "chat attachment text is unavailable")
    chunks = chunk_text(attachment.parsed_text)
    if not chunks:
        raise AIServiceError("empty_document", "document contains no indexable text")
    embedding = clients.embed(chunks)
    db.execute(
        delete(DocumentChunk).where(
            DocumentChunk.source_type == "chat_attachment",
            DocumentChunk.source_id == attachment.id,
        )
    )
    for index, (chunk, vector) in enumerate(zip(chunks, embedding.vectors, strict=True)):
        db.add(
            DocumentChunk(
                source_type="chat_attachment",
                source_id=attachment.id,
                owner_id=attachment.owner_id,
                chunk_index=index,
                content=chunk,
                content_hash=hashlib.sha256(chunk.encode("utf-8")).hexdigest(),
                embedding=vector,
                metadata_json=json.dumps(
                    {"model": embedding.model, "title": attachment.original_name},
                    ensure_ascii=False,
                ),
            )
        )
    attachment.parse_status = "ready"
    attachment.parse_error = None
    db.flush()
    return {"chunk_count": len(chunks), "model": embedding.model}


def _speech_transcription(
    task: AITask, clients: LocalAIClients, settings: Settings
) -> dict[str, object]:
    reference = str(task.input_data.get("storage_ref") or task.input_data.get("path", ""))
    media_type = str(task.input_data.get("media_type", "application/octet-stream"))
    suffix = Path(reference).suffix or ".audio"
    with build_storage(settings).materialize(reference, suffix=suffix) as path:
        return clients.transcribe(path, media_type=media_type).model_dump(mode="json")


def _speech_synthesis(
    db: Session,
    task: AITask,
    clients: LocalAIClients,
    settings: Settings,
) -> dict[str, object]:
    text = str(task.input_data.get("text", "")).strip()
    if not text or task.owner_id is None:
        raise AIServiceError("invalid_synthesis_task", "synthesis input is invalid")
    audio = clients.synthesize(text)
    storage = build_storage(settings)
    storage_ref = storage.put_bytes(
        f"media/{uuid4().hex}.wav",
        audio,
        media_type="audio/wav",
    )
    artifact = MediaArtifact(
        owner_id=task.owner_id,
        session_id=(
            str(task.input_data["session_id"]) if task.input_data.get("session_id") else None
        ),
        chat_session_id=(
            str(task.input_data["chat_session_id"])
            if task.input_data.get("chat_session_id")
            else None
        ),
        kind="speech_synthesis",
        media_type="audio/wav",
        storage_path=storage_ref,
        size_bytes=len(audio),
        expires_at=utc_now() + timedelta(days=settings.audio_retention_days),
    )
    db.add(artifact)
    db.flush()
    return {"artifact_id": artifact.id, "media_type": artifact.media_type}


def process_task(
    db: Session,
    task: AITask,
    *,
    clients: LocalAIClients,
    settings: Settings,
    agent_gateway: AgentGateway | None = None,
    conversation_gateway: ConversationGateway | None = None,
    tool_registry: ToolRegistry | None = None,
) -> dict[str, object]:
    if task.task_type == AITaskType.profile_analysis:
        return _profile_analysis(
            db,
            task,
            agent_gateway
            or build_agent_gateway(settings, db=db, owner_id=task.owner_id),
        )
    if task.task_type == AITaskType.resume_ocr:
        return _resume_ocr(db, task, clients, settings)
    if task.task_type == AITaskType.document_embedding:
        return _document_embedding(db, task, clients)
    if task.task_type in {AITaskType.speech_transcription, AITaskType.chat_transcription}:
        return _speech_transcription(task, clients, settings)
    if task.task_type in {AITaskType.speech_synthesis, AITaskType.chat_synthesis}:
        return _speech_synthesis(db, task, clients, settings)
    if task.task_type == AITaskType.chat_attachment_parse:
        return _chat_attachment_ocr(db, task, clients, settings)
    if task.task_type == AITaskType.chat_attachment_embedding:
        return _chat_attachment_embedding(db, task, clients)
    if task.task_type == AITaskType.chat_agent_run:
        from app.chat.worker import handle_chat_agent_run

        run_id = str(task.input_data.get("run_id", ""))

        return handle_chat_agent_run(
            db,
            task,
            gateway=conversation_gateway
            or build_conversation_gateway(
                settings,
                db=db,
                owner_id=task.owner_id,
                run_id=run_id,
            ),
            registry=tool_registry or build_business_tool_registry(),
            settings=settings,
        )
    raise AIServiceError("unsupported_task", "AI task type is unsupported")


def process_next_task(
    session_factory: Callable[[], Session],
    *,
    clients: LocalAIClients,
    settings: Settings,
) -> bool:
    with session_factory() as db:
        task = claim_next_task(db, lease_seconds=settings.ai_task_lease_seconds)
        if task is None:
            db.commit()
            return False
        db.commit()
        try:
            complete_task(
                db,
                task,
                result=process_task(db, task, clients=clients, settings=settings),
            )
        except AIServiceError as error:
            fail_task(
                db,
                task,
                error_code=error.code,
                error_message=str(error),
                max_attempts=3,
                retry_delay_seconds=10,
            )
        except Exception as error:
            fail_task(
                db,
                task,
                error_code="worker_error",
                error_message=type(error).__name__,
                max_attempts=3,
                retry_delay_seconds=10,
            )
        if task.status == AITaskStatus.failed and task.task_type in {
            AITaskType.resume_ocr,
            AITaskType.document_embedding,
        }:
            resume_id = str(
                task.input_data.get("resume_id") or task.input_data.get("source_id") or ""
            )
            resume = db.get(ResumeFile, resume_id)
            if resume is not None:
                resume.parse_status = "failed"
                resume.parse_error = "AI 处理失败，可重试"
        if task.status == AITaskStatus.failed and task.task_type in {
            AITaskType.chat_attachment_parse,
            AITaskType.chat_attachment_embedding,
        }:
            attachment_id = str(task.input_data.get("attachment_id") or "")
            attachment = db.get(ChatAttachment, attachment_id)
            if attachment is not None:
                attachment.parse_status = "failed"
                attachment.parse_error = "AI 处理失败，可重试"
        db.commit()
        return True


def run_worker() -> None:
    from app.core.model_registry import load_all_models
    from app.observability.tracing import configure_tracing

    load_all_models()
    settings = get_settings()
    configure_tracing(
        enabled=settings.otel_enabled,
        service_name=f"{settings.otel_service_name}-worker",
        endpoint=settings.otel_exporter_otlp_endpoint or None,
    )
    stopping = False

    def stop(_signal_number: int, _frame: FrameType | None) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    with LocalAIClients(settings) as clients:
        while not stopping:
            if not process_next_task(SessionLocal, clients=clients, settings=settings):
                time.sleep(settings.ai_task_poll_seconds)


if __name__ == "__main__":
    run_worker()
