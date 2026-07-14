from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, EntityMixin


class InterviewSession(EntityMixin, Base):
    __tablename__ = "interview_sessions"

    student_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    resume_id: Mapped[str] = mapped_column(ForeignKey("resume_files.id"))
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"))
    provider: Mapped[str] = mapped_column(String(80))
    current_question_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="active")


class InterviewTurn(EntityMixin, Base):
    __tablename__ = "interview_turns"

    session_id: Mapped[str] = mapped_column(ForeignKey("interview_sessions.id"), index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    evaluation_json: Mapped[str] = mapped_column(Text)

