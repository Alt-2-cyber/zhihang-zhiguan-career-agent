from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, EntityMixin


class Intervention(EntityMixin, Base):
    __tablename__ = "interventions"

    counselor_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="assigned", index=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
