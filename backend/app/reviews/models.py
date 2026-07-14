from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, EntityMixin


class WeeklyReviewRecord(EntityMixin, Base):
    __tablename__ = "weekly_reviews"

    student_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    provider: Mapped[str] = mapped_column(String(80))
    metrics_json: Mapped[str] = mapped_column(Text)
    insights_json: Mapped[str] = mapped_column(Text)
    actions_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="pending_confirmation")
