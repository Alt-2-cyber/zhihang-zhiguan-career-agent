import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, case, or_, select
from sqlalchemy.orm import Session

from app.ai.models import AITask, AITaskStatus, AITaskType
from app.core.config import Settings, get_settings
from app.core.errors import AppError


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


SERVER_DEMO_UNAVAILABLE_TASKS = {
    AITaskType.resume_ocr: "简历扫描件 OCR",
    AITaskType.document_embedding: "BGE-M3 向量检索",
    AITaskType.speech_transcription: "语音识别 ASR",
    AITaskType.speech_synthesis: "语音合成 TTS",
    AITaskType.chat_attachment_parse: "对话附件 OCR",
    AITaskType.chat_attachment_embedding: "对话附件 BGE-M3 向量检索",
    AITaskType.chat_transcription: "语音识别 ASR",
    AITaskType.chat_synthesis: "语音合成 TTS",
}


def is_task_available(
    task_type: AITaskType,
    *,
    settings: Settings | None = None,
) -> bool:
    selected_settings = settings or get_settings()
    return not (
        selected_settings.deployment_mode == "server-demo"
        and task_type in SERVER_DEMO_UNAVAILABLE_TASKS
    )


def ensure_task_available(
    task_type: AITaskType,
    *,
    settings: Settings | None = None,
) -> None:
    if is_task_available(task_type, settings=settings):
        return
    capability = SERVER_DEMO_UNAVAILABLE_TASKS[task_type]
    raise AppError(
        503,
        "capability_unavailable",
        f"当前服务器演示版未部署{capability}，请使用文本输入或文本简历。",
    )


def enqueue_task(
    db: Session,
    *,
    task_type: AITaskType,
    owner_id: str | None,
    input_data: dict[str, object],
    now: datetime | None = None,
) -> AITask:
    ensure_task_available(task_type)
    current = now or utc_now()
    task = AITask(
        task_type=task_type,
        owner_id=owner_id,
        status=AITaskStatus.queued,
        input_json=json.dumps(input_data, ensure_ascii=False),
        available_at=current,
    )
    db.add(task)
    db.flush()
    return task


def claim_next_task(
    db: Session,
    *,
    lease_seconds: int,
    now: datetime | None = None,
) -> AITask | None:
    current = now or utc_now()
    priority = case(
        (AITask.task_type == AITaskType.chat_agent_run, 0),
        (AITask.task_type.in_([AITaskType.chat_transcription, AITaskType.chat_synthesis]), 1),
        (
            AITask.task_type.in_(
                [AITaskType.chat_attachment_parse, AITaskType.chat_attachment_embedding]
            ),
            2,
        ),
        else_=5,
    )
    task = db.scalar(
        select(AITask)
        .where(
            or_(
                and_(
                    AITask.status == AITaskStatus.queued,
                    AITask.available_at <= current,
                ),
                and_(
                    AITask.status == AITaskStatus.running,
                    AITask.lease_expires_at < current,
                ),
            )
        )
        .order_by(priority, AITask.available_at, AITask.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if task is None:
        return None
    task.status = AITaskStatus.running
    task.attempt_count += 1
    task.heartbeat_at = current
    task.lease_expires_at = current + timedelta(seconds=lease_seconds)
    task.completed_at = None
    db.flush()
    return task


def complete_task(
    db: Session,
    task: AITask,
    *,
    result: dict[str, object],
    now: datetime | None = None,
) -> None:
    current = now or utc_now()
    task.status = AITaskStatus.succeeded
    task.result_json = json.dumps(result, ensure_ascii=False)
    task.error_code = None
    task.error_message = None
    task.lease_expires_at = None
    task.heartbeat_at = current
    task.completed_at = current
    db.flush()


def fail_task(
    db: Session,
    task: AITask,
    *,
    error_code: str,
    error_message: str,
    max_attempts: int,
    retry_delay_seconds: int,
    now: datetime | None = None,
) -> None:
    current = now or utc_now()
    task.error_code = error_code[:80]
    task.error_message = error_message[:300]
    task.lease_expires_at = None
    task.heartbeat_at = current
    if task.attempt_count < max_attempts:
        task.status = AITaskStatus.queued
        task.available_at = current + timedelta(seconds=retry_delay_seconds)
        task.completed_at = None
    else:
        task.status = AITaskStatus.failed
        task.dead_lettered_at = current
        task.completed_at = current
    db.flush()


def heartbeat_task(
    db: Session,
    task: AITask,
    *,
    lease_seconds: int,
    now: datetime | None = None,
) -> None:
    current = now or utc_now()
    task.heartbeat_at = current
    task.lease_expires_at = current + timedelta(seconds=lease_seconds)
    db.flush()
