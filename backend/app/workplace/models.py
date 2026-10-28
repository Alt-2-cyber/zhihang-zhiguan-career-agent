from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
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


class SimulationScenario(EntityMixin, Base):
    __tablename__ = "simulation_scenarios"

    title: Mapped[str] = mapped_column(String(160), index=True)
    category: Mapped[str] = mapped_column(String(60), index=True)
    difficulty: Mapped[str] = mapped_column(String(20), default="medium", index=True)
    description: Mapped[str] = mapped_column(Text)
    competencies_json: Mapped[str] = mapped_column(Text, default="[]")
    steps_json: Mapped[str] = mapped_column(Text, default="[]")
    rubric_json: Mapped[str] = mapped_column(Text, default="[]")
    mode: Mapped[str] = mapped_column(String(30), default="workplace", index=True)
    stage_definition_json: Mapped[str] = mapped_column(Text, default="[]")
    # Structured context for post-hire work scenarios. Interview scenarios can
    # leave this as an empty object; workplace scenarios use it as the task brief.
    work_context_json: Mapped[str] = mapped_column(Text, default="{}")
    safety_policy_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)


class SimulationSession(EntityMixin, Base):
    __tablename__ = "simulation_sessions"
    __table_args__ = (
        CheckConstraint(
            "score IS NULL OR (score BETWEEN 0 AND 100)", name="ck_simulation_session_score"
        ),
        Index("ix_simulation_session_student_status_updated", "student_id", "status", "updated_at"),
    )

    student_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    scenario_id: Mapped[str] = mapped_column(ForeignKey("simulation_scenarios.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)
    mode: Mapped[str] = mapped_column(String(30), default="workplace", index=True)
    stage: Mapped[str] = mapped_column(String(60), default="default", index=True)
    stress_level: Mapped[str] = mapped_column(String(20), default="light")
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assessment_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SimulationTurn(EntityMixin, Base):
    __tablename__ = "simulation_turns"
    __table_args__ = (
        UniqueConstraint("session_id", "sequence", name="uq_simulation_turn_sequence"),
        CheckConstraint("score BETWEEN 0 AND 100", name="ck_simulation_turn_score"),
    )

    session_id: Mapped[str] = mapped_column(
        ForeignKey("simulation_sessions.id", ondelete="CASCADE"), index=True
    )
    student_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    prompt: Mapped[str] = mapped_column(Text)
    response: Mapped[str] = mapped_column(Text)
    score: Mapped[int] = mapped_column(Integer)
    feedback_json: Mapped[str] = mapped_column(Text, default="{}")


class SimulationMaterialBinding(EntityMixin, Base):
    __tablename__ = "simulation_material_bindings"
    __table_args__ = (
        UniqueConstraint(
            "session_id", "source_type", "source_id", "purpose", name="uq_simulation_material_binding"
        ),
        Index("ix_simulation_material_student_created", "student_id", "created_at"),
    )

    session_id: Mapped[str] = mapped_column(
        ForeignKey("simulation_sessions.id", ondelete="CASCADE"), index=True
    )
    student_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    source_type: Mapped[str] = mapped_column(String(30), default="resume")
    source_id: Mapped[str] = mapped_column(String(36), index=True)
    purpose: Mapped[str] = mapped_column(String(60), default="answer_context")
    context_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SimulationMessage(EntityMixin, Base):
    __tablename__ = "simulation_messages"
    __table_args__ = (
        UniqueConstraint("session_id", "sequence", name="uq_simulation_message_sequence"),
        Index("ix_simulation_message_session_created", "session_id", "created_at"),
    )

    session_id: Mapped[str] = mapped_column(
        ForeignKey("simulation_sessions.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    speaker: Mapped[str] = mapped_column(String(60), index=True)
    display_name: Mapped[str] = mapped_column(String(80))
    stage: Mapped[str] = mapped_column(String(60), index=True)
    content: Mapped[str] = mapped_column(Text)
    reply_to: Mapped[str | None] = mapped_column(String(36), nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")


class WorkplaceDeliverable(EntityMixin, Base):
    """A concrete work artifact produced during a post-hire training session."""

    __tablename__ = "workplace_deliverables"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'submitted', 'reviewed')",
            name="ck_workplace_deliverable_status",
        ),
        CheckConstraint("revision >= 1", name="ck_workplace_deliverable_revision"),
        UniqueConstraint(
            "session_id", "action_type", "revision", name="uq_workplace_deliverable_revision"
        ),
        Index("ix_workplace_deliverable_student_status", "student_id", "status"),
        Index("ix_workplace_deliverable_session_updated", "session_id", "updated_at"),
    )

    session_id: Mapped[str] = mapped_column(
        ForeignKey("simulation_sessions.id", ondelete="CASCADE"), index=True
    )
    student_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    action_type: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    reviewer_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
