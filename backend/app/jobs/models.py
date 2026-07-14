from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, EntityMixin


class Job(EntityMixin, Base):
    __tablename__ = "jobs"

    title: Mapped[str] = mapped_column(String(120), index=True)
    company: Mapped[str] = mapped_column(String(160))
    location: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)


class JobMatchRecord(EntityMixin, Base):
    __tablename__ = "job_matches"

    student_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    provider: Mapped[str] = mapped_column(String(80))
    recommendation: Mapped[str] = mapped_column(String(40))
    overall_score: Mapped[int] = mapped_column(Integer)
    dimensions_json: Mapped[str] = mapped_column(Text)
    gaps_json: Mapped[str] = mapped_column(Text)
    actions_json: Mapped[str] = mapped_column(Text)
