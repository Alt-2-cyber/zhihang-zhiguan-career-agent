from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, EntityMixin


class StudentProfile(EntityMixin, Base):
    __tablename__ = "student_profiles"

    student_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    summary: Mapped[str] = mapped_column(Text)
    strengths_json: Mapped[str] = mapped_column(Text)
    gaps_json: Mapped[str] = mapped_column(Text)
    constraints_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="confirmed")
    version: Mapped[int] = mapped_column(Integer, default=1)


class ProfileAnalysisDraft(EntityMixin, Base):
    __tablename__ = "profile_analysis_drafts"

    student_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(80))
    payload_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="pending")
