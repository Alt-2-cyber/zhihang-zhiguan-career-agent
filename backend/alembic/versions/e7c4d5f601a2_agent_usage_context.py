"""Add chat-run context columns to model usage telemetry."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "e7c4d5f601a2"
down_revision: str | Sequence[str] | None = "e7b9c4d5f601"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("agent_model_calls")}
    if "run_id" not in columns:
        op.add_column("agent_model_calls", sa.Column("run_id", sa.String(length=36), nullable=True))
    if "prompt_version" not in columns:
        op.add_column(
            "agent_model_calls",
            sa.Column("prompt_version", sa.String(length=80), nullable=True),
        )
    indexes = {index["name"] for index in inspector.get_indexes("agent_model_calls")}
    if "ix_agent_model_calls_run_id" not in indexes:
        op.create_index("ix_agent_model_calls_run_id", "agent_model_calls", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_model_calls_run_id", table_name="agent_model_calls")
    op.drop_column("agent_model_calls", "prompt_version")
    op.drop_column("agent_model_calls", "run_id")
