from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.service import build_agent_gateway
from app.auth.models import User, UserRole
from app.auth.security import require_roles
from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import AppError
from app.jobs.models import Job
from app.resumes.models import ResumeFile, ResumeOptimizationDraft, ResumeVersion
from app.resumes.parser import parse_resume
from app.resumes.storage import save_upload, validate_upload

router = APIRouter(prefix="/resumes", tags=["resumes"])


class ResumeFileRead(BaseModel):
    id: str
    original_name: str
    stored_name: str
    media_type: str
    size_bytes: int
    parse_status: str


class ResumeOptimizationRequest(BaseModel):
    job_id: str


class ResumeOptimizationRead(BaseModel):
    id: str
    provider: str
    status: str
    suggestions: list[dict[str, object]]


@router.get("", response_model=list[ResumeFileRead])
def list_resumes(
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> list[ResumeFile]:
    return list(
        db.scalars(
            select(ResumeFile)
            .where(ResumeFile.student_id == current_user.id)
            .order_by(ResumeFile.created_at.desc())
        ).all()
    )


@router.post("", response_model=ResumeFileRead, status_code=status.HTTP_201_CREATED)
def upload_resume(
    file: UploadFile = File(...),
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> ResumeFile:
    settings = get_settings()
    content = file.file.read(settings.max_upload_size_mb * 1024 * 1024 + 1)
    extension = validate_upload(
        file.filename or "",
        file.content_type or "application/octet-stream",
        content,
        max_bytes=settings.max_upload_size_mb * 1024 * 1024,
    )
    stored_name, path = save_upload(content, extension, Path(settings.upload_dir))
    parse_status = "parsed"
    parsed_text: str | None = None
    parse_error: str | None = None
    try:
        parsed_text = parse_resume(path)
        if not parsed_text:
            raise ValueError("简历未包含可读取文本")
    except Exception:
        parse_status = "failed"
        parse_error = "文件解析失败，请粘贴简历文本或上传其他文件"

    resume = ResumeFile(
        student_id=current_user.id,
        original_name=Path(file.filename or "resume").name,
        stored_name=stored_name,
        media_type=file.content_type or "application/octet-stream",
        size_bytes=len(content),
        storage_path=str(path),
        parse_status=parse_status,
        parsed_text=parsed_text,
        parse_error=parse_error,
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


@router.post(
    "/{resume_id}/optimizations",
    response_model=ResumeOptimizationRead,
    status_code=status.HTTP_201_CREATED,
)
def optimize_resume(
    resume_id: str,
    payload: ResumeOptimizationRequest,
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    import json

    resume = db.get(ResumeFile, resume_id)
    job = db.get(Job, payload.job_id)
    if resume is None or resume.student_id != current_user.id:
        raise AppError(404, "resume_not_found", "简历不存在")
    if job is None:
        raise AppError(404, "job_not_found", "岗位不存在")
    if not resume.parsed_text:
        raise AppError(409, "resume_not_parsed", "简历尚未成功解析")
    result = build_agent_gateway(get_settings()).optimize_resume(
        resume.parsed_text, job.description
    )
    suggestions = [item.model_dump(mode="json") for item in result.suggestions]
    draft = ResumeOptimizationDraft(
        student_id=current_user.id,
        resume_id=resume.id,
        job_id=job.id,
        provider=result.provider,
        suggestions_json=json.dumps(suggestions, ensure_ascii=False),
        status="pending",
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return {
        "id": draft.id,
        "provider": draft.provider,
        "status": draft.status,
        "suggestions": suggestions,
    }


@router.post("/optimizations/{draft_id}/confirm")
def confirm_resume_optimization(
    draft_id: str,
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    draft = db.get(ResumeOptimizationDraft, draft_id)
    if draft is None or draft.student_id != current_user.id:
        raise AppError(404, "optimization_not_found", "简历优化草稿不存在")
    if draft.status != "pending":
        raise AppError(409, "optimization_already_confirmed", "简历优化已确认")
    version = ResumeVersion(
        student_id=current_user.id,
        source_resume_id=draft.resume_id,
        job_id=draft.job_id,
        suggestions_json=draft.suggestions_json,
        version_number=1,
    )
    draft.status = "confirmed"
    db.add(version)
    db.commit()
    db.refresh(version)
    return {"id": version.id, "status": "confirmed", "version_number": version.version_number}
