from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, EntityMixin


class JobSource(EntityMixin, Base):
    __tablename__ = "job_sources"
    __table_args__ = (UniqueConstraint("base_url", name="uq_job_source_base_url"),)

    name: Mapped[str] = mapped_column(String(120), unique=True)
    base_url: Mapped[str] = mapped_column(String(1000))
    source_type: Mapped[str] = mapped_column(String(30), default="public_web", index=True)
    adapter_key: Mapped[str] = mapped_column(String(80), default="manual-public", index=True)
    access_policy: Mapped[str] = mapped_column(String(30), default="manual", index=True)
    terms_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)
    refresh_interval_hours: Mapped[int] = mapped_column(Integer, default=24)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class JobCrawlRecord(EntityMixin, Base):
    __tablename__ = "job_crawl_records"
    __table_args__ = (
        Index("ix_job_crawl_source_status_started", "source_id", "status", "started_at"),
    )

    source_id: Mapped[str] = mapped_column(
        ForeignKey("job_sources.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    items_seen: Mapped[int] = mapped_column(Integer, default=0)
    items_imported: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(300), nullable=True)
    details_json: Mapped[str] = mapped_column(Text, default="{}")
