"""add interview type

Revision ID: d2a1d3f4b5c6
Revises: 75bc1841affe
Create Date: 2026-08-06 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d2a1d3f4b5c6"
down_revision: str | Sequence[str] | None = "75bc1841affe"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "interview_sessions",
        sa.Column("interview_type", sa.String(length=30), server_default="standard", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("interview_sessions", "interview_type")
