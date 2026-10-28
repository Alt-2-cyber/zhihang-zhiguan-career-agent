from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, EntityMixin


class InterviewSession(EntityMixin, Base):
    __tablename__ = "interview_sessions"

    student_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    resume_id: Mapped[str] = mapped_column(ForeignKey("resume_files.id"))
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"))
    interview_type: Mapped[str] = mapped_column(
        String(30), default="standard", server_default="standard"
    )
    provider: Mapped[str] = mapped_column(String(80))
    question_plan_json: Mapped[str] = mapped_column(Text, default="[]")
    current_question_json: Mapped[str] = mapped_column(Text)
    current_core_index: Mapped[int] = mapped_column(Integer, default=0)
    current_question_kind: Mapped[str] = mapped_column(String(20), default="core")
    follow_up_count: Mapped[int] = mapped_column(Integer, default=0)
    total_turns: Mapped[int] = mapped_column(Integer, default=0)
    max_follow_ups: Mapped[int] = mapped_column(Integer, default=2)
    core_question_count: Mapped[int] = mapped_column(Integer, default=6)
    rubric_version: Mapped[str] = mapped_column(String(40), default="interview-v1")
    rubric_json: Mapped[str] = mapped_column(Text, default="[]")
    final_report_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    emotion_samples_json: Mapped[str] = mapped_column(Text, default="[]")
    emotion_summary_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="active")


class InterviewTurn(EntityMixin, Base):
    __tablename__ = "interview_turns"

    session_id: Mapped[str] = mapped_column(ForeignKey("interview_sessions.id"), index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    evaluation_json: Mapped[str] = mapped_column(Text)
    emotion_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    assistant_content: Mapped[str | None] = mapped_column(Text, nullable=True)
