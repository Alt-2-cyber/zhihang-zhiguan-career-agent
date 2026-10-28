from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, EntityMixin


class EmploymentRecord(EntityMixin, Base):
    __tablename__ = "employment_records"
    __table_args__ = (
        UniqueConstraint("application_id", name="uq_employment_application"),
        Index("ix_employment_student_status_onboard", "student_id", "status", "onboard_date"),
    )

    student_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), unique=True)
    company: Mapped[str] = mapped_column(String(160), index=True)
    job_title: Mapped[str] = mapped_column(String(120), index=True)
    onboard_date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(30), default="employed", index=True)
    student_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    employer_invitation_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    ended_at: Mapped[date | None] = mapped_column(Date, nullable=True)


class FollowupSurvey(EntityMixin, Base):
    __tablename__ = "followup_surveys"
    __table_args__ = (
        UniqueConstraint("employment_id", "milestone", name="uq_followup_milestone"),
        Index("ix_followup_status_due", "status", "due_date"),
    )

    employment_id: Mapped[str] = mapped_column(
        ForeignKey("employment_records.id", ondelete="CASCADE"), index=True
    )
    student_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    milestone: Mapped[str] = mapped_column(String(20))
    due_date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(30), default="scheduled", index=True)
    student_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    employer_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class EmployerInvitation(EntityMixin, Base):
    __tablename__ = "employer_invitations"

    employment_id: Mapped[str] = mapped_column(
        ForeignKey("employment_records.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EmployerReview(EntityMixin, Base):
    __tablename__ = "employer_reviews"
    __table_args__ = (
        UniqueConstraint("employment_id", name="uq_employer_review_employment"),
        CheckConstraint("overall_score BETWEEN 1 AND 5", name="ck_employer_review_score"),
    )

    employment_id: Mapped[str] = mapped_column(
        ForeignKey("employment_records.id", ondelete="CASCADE"), index=True
    )
    scores_json: Mapped[str] = mapped_column(Text)
    overall_score: Mapped[int] = mapped_column(Integer)
    trial_result: Mapped[str] = mapped_column(String(40))
    strengths: Mapped[str] = mapped_column(Text)
    improvement: Mapped[str] = mapped_column(Text)
    curriculum_suggestion: Mapped[str | None] = mapped_column(Text, nullable=True)
    moderation_status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class EmployeeFeedback(EntityMixin, Base):
    __tablename__ = "employee_feedback"
    __table_args__ = (
        UniqueConstraint("employment_id", name="uq_employee_feedback_employment"),
        CheckConstraint("overall_score BETWEEN 1 AND 5", name="ck_employee_feedback_score"),
    )

    employment_id: Mapped[str] = mapped_column(
        ForeignKey("employment_records.id", ondelete="CASCADE"), index=True
    )
    student_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    scores_json: Mapped[str] = mapped_column(Text)
    overall_score: Mapped[int] = mapped_column(Integer)
    requirements: Mapped[str] = mapped_column(Text)
    experience: Mapped[str] = mapped_column(Text)
    recommendation: Mapped[str] = mapped_column(Text)
    would_recommend: Mapped[bool] = mapped_column(Boolean)
    moderation_status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class InterviewExperience(EntityMixin, Base):
    __tablename__ = "interview_experiences"
    __table_args__ = (
        UniqueConstraint("employment_id", name="uq_interview_experience_employment"),
        CheckConstraint("difficulty BETWEEN 1 AND 5", name="ck_interview_experience_difficulty"),
    )

    employment_id: Mapped[str] = mapped_column(
        ForeignKey("employment_records.id", ondelete="CASCADE"), index=True
    )
    student_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    difficulty: Mapped[int] = mapped_column(Integer)
    rounds: Mapped[int] = mapped_column(Integer)
    process: Mapped[str] = mapped_column(Text)
    questions: Mapped[str] = mapped_column(Text)
    advice: Mapped[str] = mapped_column(Text)
    moderation_status: Mapped[str] = mapped_column(String(30), default="pending", index=True)


class FeedbackModeration(EntityMixin, Base):
    __tablename__ = "feedback_moderation"
    __table_args__ = (
        Index("ix_feedback_moderation_target", "feedback_type", "feedback_id", "created_at"),
    )

    feedback_type: Mapped[str] = mapped_column(String(30), index=True)
    feedback_id: Mapped[str] = mapped_column(String(36), index=True)
    reviewer_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    decision: Mapped[str] = mapped_column(String(30), index=True)
    reason: Mapped[str] = mapped_column(String(500))
