"""Persist server-side interview emotion observations without storing camera frames."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "c1d2e3f4a5b6"
down_revision: str | Sequence[str] | None = "b8e1f4c62a30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    session_columns = {item["name"] for item in inspector.get_columns("interview_sessions")}
    if "emotion_samples_json" not in session_columns:
        op.add_column(
            "interview_sessions",
            sa.Column("emotion_samples_json", sa.Text(), nullable=False, server_default="[]"),
        )
    if "emotion_summary_json" not in session_columns:
        op.add_column(
            "interview_sessions",
            sa.Column("emotion_summary_json", sa.Text(), nullable=True),
        )

    turn_columns = {item["name"] for item in inspector.get_columns("interview_turns")}
    if "emotion_json" not in turn_columns:
        op.add_column("interview_turns", sa.Column("emotion_json", sa.Text(), nullable=True))


def downgrade() -> None:
    # Keep the migration non-destructive so old interview reports remain readable.
    pass
