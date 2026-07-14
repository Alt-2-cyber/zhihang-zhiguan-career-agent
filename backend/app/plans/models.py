from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, EntityMixin


class CareerPlanRecord(EntityMixin, Base):
    __tablename__ = "career_plans"

    student_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    provider: Mapped[str] = mapped_column(String(80))
    primary_role: Mapped[str] = mapped_column(String(100))
    backup_roles_json: Mapped[str] = mapped_column(Text)
    rationale: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="pending_confirmation")


class PlanTaskRecord(EntityMixin, Base):
    __tablename__ = "plan_tasks"

    plan_id: Mapped[str] = mapped_column(ForeignKey("career_plans.id"), index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    week: Mapped[int] = mapped_column(Integer)
    due_date: Mapped[date] = mapped_column(Date)
    acceptance_criteria: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(30), default="pending")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
