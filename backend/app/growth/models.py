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


class Course(EntityMixin, Base):
    __tablename__ = "courses"

    title: Mapped[str] = mapped_column(String(160), index=True)
    provider: Mapped[str] = mapped_column(String(120), index=True)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    delivery_mode: Mapped[str] = mapped_column(String(30), default="online")
    duration_minutes: Mapped[int] = mapped_column(Integer)
    skills_json: Mapped[str] = mapped_column(Text, default="[]")
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SkillGap(EntityMixin, Base):
    __tablename__ = "skill_gaps"
    __table_args__ = (
        UniqueConstraint("student_id", "skill_name", name="uq_skill_gap_student_skill"),
        CheckConstraint("current_level BETWEEN 0 AND 100", name="ck_skill_gap_current"),
        CheckConstraint("target_level BETWEEN 0 AND 100", name="ck_skill_gap_target"),
    )

    student_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    skill_name: Mapped[str] = mapped_column(String(100), index=True)
    current_level: Mapped[int] = mapped_column(Integer)
    target_level: Mapped[int] = mapped_column(Integer)
    evidence_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(30), default="open", index=True)


class LearningPlan(EntityMixin, Base):
    __tablename__ = "learning_plans"
    __table_args__ = (
        Index("ix_learning_plan_student_status_updated", "student_id", "status", "updated_at"),
    )

    student_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    target_role: Mapped[str] = mapped_column(String(120))
    rationale: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)


class LearningTask(EntityMixin, Base):
    __tablename__ = "learning_tasks"
    __table_args__ = (
        Index("ix_learning_task_student_status_due", "student_id", "status", "due_date"),
    )

    plan_id: Mapped[str] = mapped_column(
        ForeignKey("learning_plans.id", ondelete="CASCADE"), index=True
    )
    student_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    course_id: Mapped[str | None] = mapped_column(
        ForeignKey("courses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    skill_name: Mapped[str] = mapped_column(String(100), index=True)
    title: Mapped[str] = mapped_column(String(160))
    due_date: Mapped[date] = mapped_column(Date, index=True)
    acceptance_criteria: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    evidence_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    completion_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LearningExam(EntityMixin, Base):
    __tablename__ = "learning_exams"
    __table_args__ = (
        CheckConstraint("question_count BETWEEN 1 AND 20", name="ck_learning_exam_count"),
        CheckConstraint("passing_score BETWEEN 0 AND 100", name="ck_learning_exam_passing"),
        CheckConstraint("duration_minutes BETWEEN 5 AND 90", name="ck_learning_exam_duration"),
        CheckConstraint(
            "latest_score IS NULL OR (latest_score BETWEEN 0 AND 100)",
            name="ck_learning_exam_latest_score",
        ),
        Index("ix_learning_exam_student_status_updated", "student_id", "status", "updated_at"),
    )

    student_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    course_id: Mapped[str | None] = mapped_column(
        ForeignKey("courses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    task_id: Mapped[str | None] = mapped_column(
        ForeignKey("learning_tasks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(180))
    skill_name: Mapped[str] = mapped_column(String(100), index=True)
    generated_by: Mapped[str] = mapped_column(String(80), default="local-ai-exam-generator")
    prompt_version: Mapped[str] = mapped_column(String(40), default="exam-v1")
    source_context_json: Mapped[str] = mapped_column(Text, default="{}")
    generation_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="generated", index=True)
    question_count: Mapped[int] = mapped_column(Integer)
    passing_score: Mapped[int] = mapped_column(Integer, default=60)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=20)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    latest_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latest_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class QuestionBankItem(EntityMixin, Base):
    __tablename__ = "question_bank_items"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending_review', 'approved', 'rejected', 'retired')",
            name="ck_question_bank_status",
        ),
        Index("ix_question_bank_skill_status", "skill_name", "status", "updated_at"),
    )

    skill_name: Mapped[str] = mapped_column(String(100), index=True)
    course_id: Mapped[str | None] = mapped_column(
        ForeignKey("courses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    prompt: Mapped[str] = mapped_column(Text)
    options_json: Mapped[str] = mapped_column(Text)
    correct_answer: Mapped[str] = mapped_column(String(20))
    explanation: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(40), default="agent")
    generated_by: Mapped[str] = mapped_column(String(80), default="unknown")
    prompt_version: Mapped[str] = mapped_column(String(80), default="exam-v1")
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(30), default="pending_review", index=True)
    reviewed_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class QuestionBankReview(EntityMixin, Base):
    __tablename__ = "question_bank_reviews"

    item_id: Mapped[str] = mapped_column(
        ForeignKey("question_bank_items.id", ondelete="CASCADE"), index=True
    )
    reviewer_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    previous_status: Mapped[str] = mapped_column(String(30))
    decision: Mapped[str] = mapped_column(String(30), index=True)
    reason: Mapped[str] = mapped_column(String(1_000))


class LearningExamQuestion(EntityMixin, Base):
    __tablename__ = "learning_exam_questions"
    __table_args__ = (
        UniqueConstraint("exam_id", "sequence", name="uq_learning_exam_question_sequence"),
    )

    exam_id: Mapped[str] = mapped_column(
        ForeignKey("learning_exams.id", ondelete="CASCADE"), index=True
    )
    question_bank_item_id: Mapped[str | None] = mapped_column(
        ForeignKey("question_bank_items.id", ondelete="SET NULL"), nullable=True, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    question_type: Mapped[str] = mapped_column(String(30), default="single_choice")
    prompt: Mapped[str] = mapped_column(Text)
    options_json: Mapped[str] = mapped_column(Text)
    correct_answer: Mapped[str] = mapped_column(String(20))
    explanation: Mapped[str] = mapped_column(Text)


class LearningExamSubmission(EntityMixin, Base):
    __tablename__ = "learning_exam_submissions"
    __table_args__ = (
        CheckConstraint("score BETWEEN 0 AND 100", name="ck_learning_exam_submission_score"),
        Index("ix_learning_exam_submission_student_created", "student_id", "created_at"),
    )

    exam_id: Mapped[str] = mapped_column(
        ForeignKey("learning_exams.id", ondelete="CASCADE"), index=True
    )
    student_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    answers_json: Mapped[str] = mapped_column(Text)
    score: Mapped[int] = mapped_column(Integer)
    passed: Mapped[bool] = mapped_column(Boolean)
    results_json: Mapped[str] = mapped_column(Text)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class QuestionFavorite(EntityMixin, Base):
    __tablename__ = "question_favorites"
    __table_args__ = (
        UniqueConstraint("student_id", "question_id", name="uq_question_favorite_student_question"),
        Index("ix_question_favorite_student_created", "student_id", "created_at"),
    )

    student_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[str] = mapped_column(
        ForeignKey("learning_exam_questions.id", ondelete="CASCADE"), index=True
    )


class LearningMistake(EntityMixin, Base):
    __tablename__ = "learning_mistakes"
    __table_args__ = (
        UniqueConstraint("student_id", "question_id", name="uq_learning_mistake_student_question"),
        Index("ix_learning_mistake_student_status_updated", "student_id", "status", "updated_at"),
    )

    student_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    exam_id: Mapped[str] = mapped_column(
        ForeignKey("learning_exams.id", ondelete="CASCADE"), index=True
    )
    question_id: Mapped[str] = mapped_column(
        ForeignKey("learning_exam_questions.id", ondelete="CASCADE"), index=True
    )
    skill_name: Mapped[str] = mapped_column(String(100), index=True)
    selected_answer: Mapped[str] = mapped_column(String(20), default="")
    correct_answer: Mapped[str] = mapped_column(String(20))
    explanation: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="open", index=True)
    last_submission_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
