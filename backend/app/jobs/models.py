from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, EntityMixin


class Job(EntityMixin, Base):
    __tablename__ = "jobs"

    title: Mapped[str] = mapped_column(String(120), index=True)
    company: Mapped[str] = mapped_column(String(160))
    location: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    source_kind: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    source_host: Mapped[str | None] = mapped_column(String(253), nullable=True)
    source_trust_level: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_trust_score: Mapped[float | None] = mapped_column(nullable=True)
    source_fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)


class JobMatchRecord(EntityMixin, Base):
    __tablename__ = "job_matches"

    student_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    provider: Mapped[str] = mapped_column(String(80))
    rubric_version: Mapped[str] = mapped_column(String(40), default="match-v2")
    recommendation: Mapped[str] = mapped_column(String(40))
    overall_score: Mapped[int] = mapped_column(Integer)
    dimensions_json: Mapped[str] = mapped_column(Text)
    gaps_json: Mapped[str] = mapped_column(Text)
    actions_json: Mapped[str] = mapped_column(Text)
