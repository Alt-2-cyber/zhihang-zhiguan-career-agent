from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, EntityMixin


class RiskEvent(EntityMixin, Base):
    __tablename__ = "risk_events"
    __table_args__ = (
        UniqueConstraint("student_id", "rule_code", "status", name="uq_active_student_risk"),
    )

    student_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    rule_code: Mapped[str] = mapped_column(String(80), index=True)
    level: Mapped[str] = mapped_column(String(30), index=True)
    facts_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="open", index=True)
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
