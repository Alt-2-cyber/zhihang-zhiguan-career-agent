from pathlib import Path
from uuid import uuid4

from app.core.errors import AppError

ALLOWED_UPLOADS = {
    ".pdf": {"application/pdf"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",
    },
}


def validate_upload(filename: str, media_type: str, content: bytes, *, max_bytes: int) -> str:
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_UPLOADS or media_type not in ALLOWED_UPLOADS[extension]:
        raise AppError(415, "unsupported_resume", "仅支持 PDF 或 DOCX 简历")
    if len(content) > max_bytes:
        raise AppError(413, "resume_too_large", "简历文件大小超过限制")
    return extension


def save_upload(content: bytes, extension: str, upload_dir: Path) -> tuple[str, Path]:
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid4().hex}{extension}"
    target = (upload_dir / stored_name).resolve()
    root = upload_dir.resolve()
    if root not in target.parents:
        raise AppError(400, "invalid_upload_path", "文件保存路径无效")
    target.write_bytes(content)
    return stored_name, target
