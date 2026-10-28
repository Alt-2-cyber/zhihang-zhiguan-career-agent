import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.models import AITask, AITaskStatus, AITaskType, MediaArtifact
from app.ai.service import utc_now
from app.audit.models import AuditLog
from app.auth.models import User, UserRole
from app.auth.security import get_current_user, require_roles
from app.core.config import get_settings
from app.core.database import SessionLocal, get_db
from app.core.errors import AppError
from app.resumes.models import ResumeFile
from app.resumes.storage import StorageService, build_storage

router = APIRouter(prefix="/ai", tags=["ai-runtime"])


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _serialize_task(task: AITask) -> dict[str, object]:
    return {
        "id": task.id,
        "task_type": task.task_type,
        "status": task.status,
        "result": task.result_data,
        "error": (
            {"code": task.error_code, "message": task.error_message} if task.error_code else None
        ),
        "attempt_count": task.attempt_count,
        "dead_lettered_at": task.dead_lettered_at,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "completed_at": task.completed_at,
    }


@router.get("/tasks/{task_id}")
def read_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    task = db.get(AITask, task_id)
    if task is None or task.owner_id != current_user.id:
        raise AppError(404, "task_not_found", "AI 任务不存在")
    return _serialize_task(task)


@router.post("/tasks/{task_id}/retry")
def retry_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    task = db.get(AITask, task_id)
    if task is None or task.owner_id != current_user.id:
        raise AppError(404, "task_not_found", "AI 任务不存在")
    if task.status != AITaskStatus.failed or task.dead_lettered_at is not None:
        raise AppError(409, "task_not_retryable", "只有失败任务可以重试")
    task.status = AITaskStatus.queued
    task.attempt_count = 0
    task.available_at = utc_now()
    task.lease_expires_at = None
    task.heartbeat_at = None
    task.completed_at = None
    task.error_code = None
    task.error_message = None
    task.dead_lettered_at = None
    if task.task_type in {AITaskType.resume_ocr, AITaskType.document_embedding}:
        resume_id = task.input_data.get("resume_id") or task.input_data.get("source_id")
        resume = db.get(ResumeFile, resume_id) if isinstance(resume_id, str) else None
        if resume is not None and resume.student_id == current_user.id:
            resume.parse_status = (
                "queued" if task.task_type == AITaskType.resume_ocr else "embedding"
            )
            resume.parse_error = None
    db.commit()
    db.refresh(task)
    return _serialize_task(task)


@router.get("/dead-letters")
def list_dead_letter_tasks(
    limit: int = 100,
    _current_user: User = Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """List terminal AI failures for an operator to inspect and replay."""
    bounded_limit = max(1, min(limit, 500))
    tasks = db.scalars(
        select(AITask)
        .where(AITask.dead_lettered_at.is_not(None))
        .order_by(AITask.dead_lettered_at.desc(), AITask.id.desc())
        .limit(bounded_limit)
    ).all()
    return {"items": [_serialize_task(task) for task in tasks], "count": len(tasks)}


@router.post("/dead-letters/{task_id}/retry")
def retry_dead_letter_task(
    task_id: str,
    current_user: User = Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    task = db.get(AITask, task_id)
    if task is None or task.dead_lettered_at is None:
        raise AppError(404, "dead_letter_not_found", "死信任务不存在")
    if task.status != AITaskStatus.failed:
        raise AppError(409, "dead_letter_not_retryable", "当前死信任务状态不能重试")
    previous = {
        "attempt_count": task.attempt_count,
        "error_code": task.error_code,
        "error_message": task.error_message,
        "dead_lettered_at": task.dead_lettered_at.isoformat(),
    }
    task.status = AITaskStatus.queued
    task.attempt_count = 0
    task.available_at = utc_now()
    task.lease_expires_at = None
    task.heartbeat_at = None
    task.completed_at = None
    task.error_code = None
    task.error_message = None
    task.dead_lettered_at = None
    db.add(
        AuditLog(
            user_id=current_user.id,
            action="ai.dead_letter_retried",
            resource_type="ai_task",
            resource_id=task.id,
            details=json.dumps(previous, ensure_ascii=False),
        )
    )
    db.commit()
    db.refresh(task)
    return _serialize_task(task)


@router.get("/media/{artifact_id}", response_class=Response)
def download_media(
    artifact_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    artifact = db.get(MediaArtifact, artifact_id)
    if artifact is None or artifact.owner_id != current_user.id:
        raise AppError(404, "media_not_found", "音频不存在")
    if _aware(artifact.expires_at) <= utc_now():
        raise AppError(410, "media_expired", "音频已过期")
    try:
        content = build_storage(get_settings()).read_bytes(
            artifact.storage_path,
            allow_external_local=True,
        )
    except (FileNotFoundError, OSError):
        raise AppError(404, "media_not_found", "音频不存在") from None
    return Response(
        content=content,
        media_type=artifact.media_type,
        headers={"Content-Disposition": f'attachment; filename="{artifact.id}.wav"'},
    )


def _service_readiness(url: str) -> bool:
    try:
        response = httpx.get(f"{url.rstrip('/')}/health/ready", timeout=1.5)
        return response.status_code == 200 and response.json().get("ready") is True
    except (httpx.HTTPError, ValueError):
        return False


@router.get("/capabilities")
def capabilities(_current_user: User = Depends(get_current_user)) -> dict[str, object]:
    settings = get_settings()
    provider_configs = {
        "zhipu": {
            "name": "zhipu",
            "model": settings.zhipu_model,
            "configured": bool(settings.zhipu_api_key),
        },
        "deepseek": {
            "name": "deepseek",
            "model": settings.deepseek_model,
            "configured": bool(settings.deepseek_api_key),
        },
    }
    ordered_providers = []
    seen = set()
    for item in settings.agent_provider_order.split(","):
        name = item.strip().lower()
        if name in provider_configs and name not in seen:
            ordered_providers.append(provider_configs[name])
            seen.add(name)
    for name in ("zhipu", "deepseek"):
        if name not in seen:
            ordered_providers.append(provider_configs[name])
    local_fallback_enabled = settings.agent_provider == "local" or settings.agent_allow_local_fallback
    local_provider = [{"name": "local-rules", "model": "local-demo", "configured": True}] if local_fallback_enabled else []
    service_readiness = (
        {"embedding": False, "ocr": False, "speech": False, "emotion": False}
        if settings.deployment_mode == "server-demo"
        else {
            "embedding": _service_readiness(settings.embedding_service_url),
            "ocr": _service_readiness(settings.ocr_service_url),
            "speech": _service_readiness(settings.speech_service_url),
            "emotion": _service_readiness(settings.emotion_service_url),
        }
    )
    services = {
        "embedding": {"model": "BAAI/bge-m3", "ready": service_readiness["embedding"]},
        "ocr": {"model": "PP-OCRv5", "ready": service_readiness["ocr"]},
        "speech": {
            "asr_model": "paraformer-zh",
            "tts_model": "MeloTTS-ZH",
            "ready": service_readiness["speech"],
        },
        "emotion": {
            "model": "YOLO-face + vit-face-expression",
            "ready": service_readiness["emotion"],
            "privacy": "仅保存情绪统计，不保存摄像头帧",
        },
    }
    online_agent_ready = any(provider["configured"] for provider in ordered_providers)
    limitations = (
        [
            "扫描版 PDF OCR 未部署；可读取文本的 PDF 和 DOCX 仍可尝试解析。",
            "BGE-M3 未部署，Agent 不提供语义知识库检索。",
            "FunASR 和 MeloTTS 未部署，语音输入与朗读不可用。",
            "YOLO 表情分析未部署，摄像头分析不可用。",
            "对话附件解析和向量索引未部署。",
        ]
        if settings.deployment_mode == "server-demo"
        else []
    )
    return {
        "deployment_mode": settings.deployment_mode,
        "agent": {
            "mode": settings.agent_provider,
            "strict_online": settings.agent_provider == "failover" and not settings.agent_allow_local_fallback,
            "local_fallback_enabled": local_fallback_enabled,
            "providers": ordered_providers + local_provider,
        },
        "services": services,
        "features": {
            "online_agent": online_agent_ready,
            "resume_text_extraction": True,
            "pdf_ocr": services["ocr"]["ready"],
            "semantic_search": services["embedding"]["ready"],
            "speech_transcription": services["speech"]["ready"],
            "speech_synthesis": services["speech"]["ready"],
            "camera_emotion": services["emotion"]["ready"],
            "chat_attachments": services["ocr"]["ready"] and services["embedding"]["ready"],
            "public_job_search": settings.public_job_search_enabled,
        },
        "limitations": limitations,
    }


def cleanup_expired_media(
    db: Session,
    *,
    media_root: Path,
    storage: StorageService | None = None,
    now: datetime | None = None,
) -> int:
    current = now or utc_now()
    root = media_root.resolve()
    artifacts = db.scalars(select(MediaArtifact)).all()
    removed = 0
    for artifact in artifacts:
        if _aware(artifact.expires_at) > current:
            continue
        try:
            if storage is not None and artifact.storage_path.startswith("s3://"):
                storage.delete(artifact.storage_path)
            else:
                path = Path(artifact.storage_path)
                if path.is_symlink():
                    path.unlink(missing_ok=True)
                else:
                    resolved = path.resolve()
                    if resolved == root or root in resolved.parents:
                        resolved.unlink(missing_ok=True)
                    else:
                        continue
        except OSError:
            continue
        db.delete(artifact)
        removed += 1
    db.flush()
    return removed


def cleanup_expired_media_job() -> None:
    settings = get_settings()
    with SessionLocal() as db:
        cleanup_expired_media(
            db,
            media_root=Path(settings.upload_dir) / "media",
            storage=build_storage(settings),
        )
        db.commit()
