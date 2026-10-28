import json
from datetime import datetime
from enum import StrEnum

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.encryption import EncryptedText
from app.core.models import Base, EntityMixin


class AITaskType(StrEnum):
    profile_analysis = "profile_analysis"
    resume_ocr = "resume_ocr"
    document_embedding = "document_embedding"
    speech_transcription = "speech_transcription"
    speech_synthesis = "speech_synthesis"
    chat_agent_run = "chat_agent_run"
    chat_attachment_parse = "chat_attachment_parse"
    chat_attachment_embedding = "chat_attachment_embedding"
    chat_transcription = "chat_transcription"
    chat_synthesis = "chat_synthesis"


class AITaskStatus(StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class AITask(EntityMixin, Base):
    __tablename__ = "ai_tasks"

    task_type: Mapped[str] = mapped_column(String(40), index=True)
    owner_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(30), default=AITaskStatus.queued, index=True)
    input_json: Mapped[str] = mapped_column(Text, default="{}")
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(300), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    dead_lettered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def input_data(self) -> dict[str, object]:
        return json.loads(self.input_json)

    @property
    def result_data(self) -> dict[str, object] | None:
        return json.loads(self.result_json) if self.result_json else None


class DocumentChunk(EntityMixin, Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("source_type", "source_id", "chunk_index", name="uq_document_chunk"),
    )

    source_type: Mapped[str] = mapped_column(String(40), index=True)
    source_id: Mapped[str] = mapped_column(String(36), index=True)
    owner_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(EncryptedText)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(1024).with_variant(JSON, "sqlite"))
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")


class MediaArtifact(EntityMixin, Base):
    __tablename__ = "media_artifacts"

    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[str | None] = mapped_column(
        ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=True, index=True
    )
    chat_session_id: Mapped[str | None] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=True, index=True
    )
    kind: Mapped[str] = mapped_column(String(30), index=True)
    media_type: Mapped[str] = mapped_column(String(120))
    storage_path: Mapped[str] = mapped_column(String(500), unique=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
