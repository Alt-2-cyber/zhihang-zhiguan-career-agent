from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, EntityMixin


class ResumeFile(EntityMixin, Base):
    __tablename__ = "resume_files"

    student_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    original_name: Mapped[str] = mapped_column(String(255))
    stored_name: Mapped[str] = mapped_column(String(255), unique=True)
    media_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer)
    storage_path: Mapped[str] = mapped_column(String(500))
    parse_status: Mapped[str] = mapped_column(String(30))
    parsed_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    parse_error: Mapped[str | None] = mapped_column(String(300), nullable=True)


class ResumeOptimizationDraft(EntityMixin, Base):
    __tablename__ = "resume_optimization_drafts"

    student_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    resume_id: Mapped[str] = mapped_column(ForeignKey("resume_files.id"), index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    provider: Mapped[str] = mapped_column(String(80))
    suggestions_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="pending")


class ResumeVersion(EntityMixin, Base):
    __tablename__ = "resume_versions"

    student_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    source_resume_id: Mapped[str] = mapped_column(ForeignKey("resume_files.id"), index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    suggestions_json: Mapped[str] = mapped_column(Text)
    version_number: Mapped[int] = mapped_column(Integer, default=1)
