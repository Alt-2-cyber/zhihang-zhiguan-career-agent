"""Repair the interview type column for legacy demo databases.

Some demo volumes were stamped at the current Alembic head without applying
the earlier ``d2a1d3f4b5c6`` branch.  The ORM model now writes
``interview_type`` on every interview session, so make the schema correction
explicit and idempotent for both existing and fresh databases.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a1c2d3e4f567"
down_revision: str | Sequence[str] | None = "d4b7a2c91e60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("interview_sessions")}
    if "interview_type" not in columns:
        op.add_column(
            "interview_sessions",
            sa.Column(
                "interview_type",
                sa.String(length=30),
                server_default="standard",
                nullable=False,
            ),
        )


def downgrade() -> None:
    # This revision only repairs installations that skipped d2a1d3f4b5c6.
    # Keep the column owned by that original migration when rolling back.
    pass
