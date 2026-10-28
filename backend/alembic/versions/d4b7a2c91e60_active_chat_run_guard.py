"""guard one active chat run per session

Revision ID: d4b7a2c91e60
Revises: c7a91d2e4f60
Create Date: 2026-07-15 04:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4b7a2c91e60"
down_revision: str | Sequence[str] | None = "c7a91d2e4f60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    indexes = {
        item["name"] for item in sa.inspect(op.get_bind()).get_indexes("agent_runs")
    }
    if "uq_agent_runs_active_session" in indexes:
        return
    op.create_index(
        "uq_agent_runs_active_session",
        "agent_runs",
        ["session_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
        sqlite_where=sa.text("status IN ('queued', 'running')"),
    )


def downgrade() -> None:
    op.drop_index("uq_agent_runs_active_session", table_name="agent_runs")
