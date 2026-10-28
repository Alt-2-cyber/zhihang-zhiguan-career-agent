from pathlib import Path

from sqlalchemy.orm import Session

from app.ai.models import AITaskType
from app.ai.service import enqueue_task, ensure_task_available
from app.auth.models import User
from app.chat.models import ChatAttachment, ChatSession
from app.core.config import Settings
from app.core.errors import AppError
from app.resumes.parser import parse_resume
from app.resumes.storage import build_storage, save_upload

ATTACHMENT_MEDIA = {
    ".pdf": {"application/pdf"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",
    },
    ".txt": {"text/plain", "application/octet-stream"},
}


def create_chat_attachment(
    db: Session,
    *,
    user: User,
    chat_session: ChatSession,
    filename: str,
    media_type: str,
    content: bytes,
    settings: Settings,
) -> tuple[ChatAttachment, str]:
    extension = Path(filename).suffix.lower()
    if extension not in ATTACHMENT_MEDIA or media_type not in ATTACHMENT_MEDIA[extension]:
        raise AppError(415, "unsupported_chat_attachment", "仅支持 PDF、DOCX 或 TXT 附件")
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if not content or len(content) > max_bytes:
        raise AppError(413, "chat_attachment_too_large", "附件为空或超过大小限制")
    task_type = (
        AITaskType.chat_attachment_parse
        if extension == ".pdf"
        else AITaskType.chat_attachment_embedding
    )
    ensure_task_available(task_type, settings=settings)
    storage = build_storage(settings)
    attachment_dir = Path(settings.upload_dir) / "chat" / chat_session.id
    _stored_name, storage_ref = save_upload(
        content,
        extension,
        attachment_dir,
        storage=storage,
        key_prefix=f"chat/{chat_session.id}",
    )
    parse_status = "queued" if extension == ".pdf" else "embedding"
    parsed_text: str | None = None
    if extension == ".docx":
        try:
            with storage.materialize(storage_ref, suffix=extension) as path:
                parsed_text = parse_resume(path)
        except Exception as error:
            raise AppError(422, "chat_attachment_parse_failed", "DOCX 附件解析失败") from error
    elif extension == ".txt":
        try:
            parsed_text = content.decode("utf-8").strip()
        except UnicodeDecodeError as error:
            raise AppError(422, "chat_attachment_parse_failed", "TXT 附件必须使用 UTF-8") from error
    if extension != ".pdf" and not parsed_text:
        raise AppError(422, "chat_attachment_parse_failed", "附件没有可读取文字")
    attachment = ChatAttachment(
        session_id=chat_session.id,
        owner_id=user.id,
        original_name=Path(filename).name,
        storage_path=storage_ref,
        media_type=media_type,
        size_bytes=len(content),
        parse_status=parse_status,
        parsed_text=parsed_text,
    )
    db.add(attachment)
    db.flush()
    task = enqueue_task(
        db,
        task_type=task_type,
        owner_id=user.id,
        input_data={"attachment_id": attachment.id},
    )
    attachment.ai_task_id = task.id
    return attachment, task.id
