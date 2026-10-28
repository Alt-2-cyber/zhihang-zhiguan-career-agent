"""record Agent model call telemetry for the operations dashboard"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e7b9c4d5f601"
down_revision: str | Sequence[str] | None = "f8b4d1e7c903"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "agent_model_calls" not in tables:
        op.create_table(
            "agent_model_calls",
            sa.Column("run_id", sa.String(length=36), nullable=True),
            sa.Column("owner_id", sa.String(length=36), nullable=True),
            sa.Column("operation", sa.String(length=80), nullable=False),
            sa.Column("provider", sa.String(length=80), nullable=False),
            sa.Column("model", sa.String(length=120), nullable=False),
            sa.Column("prompt_version", sa.String(length=80), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False),
            sa.Column("input_tokens", sa.Integer(), nullable=True),
            sa.Column("output_tokens", sa.Integer(), nullable=True),
            sa.Column("total_tokens", sa.Integer(), nullable=True),
            sa.Column("cost_micros", sa.Integer(), nullable=True),
            sa.Column("latency_ms", sa.Integer(), nullable=True),
            sa.Column("request_id", sa.String(length=160), nullable=True),
            sa.Column("error_code", sa.String(length=80), nullable=True),
            sa.Column("error_message", sa.String(length=300), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )

    # Older local-runtime volumes already contain this table.  Keep all
    # existing rows and only add indexes needed by the current dashboard.
    indexes = {index["name"] for index in inspector.get_indexes("agent_model_calls")}
    if "ix_agent_model_calls_owner_id" not in indexes:
        op.create_index("ix_agent_model_calls_owner_id", "agent_model_calls", ["owner_id"])
    if "ix_agent_model_calls_operation" not in indexes:
        op.create_index("ix_agent_model_calls_operation", "agent_model_calls", ["operation"])
    if "ix_agent_model_calls_provider" not in indexes:
        op.create_index("ix_agent_model_calls_provider", "agent_model_calls", ["provider"])
    if "ix_agent_model_calls_status" not in indexes:
        op.create_index("ix_agent_model_calls_status", "agent_model_calls", ["status"])
    if "ix_agent_model_calls_completed_at" not in indexes:
        op.create_index("ix_agent_model_calls_completed_at", "agent_model_calls", ["completed_at"])
    if "ix_agent_model_calls_run_id" not in indexes:
        op.create_index("ix_agent_model_calls_run_id", "agent_model_calls", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_model_calls_completed_at", table_name="agent_model_calls")
    op.drop_index("ix_agent_model_calls_status", table_name="agent_model_calls")
    op.drop_index("ix_agent_model_calls_provider", table_name="agent_model_calls")
    op.drop_index("ix_agent_model_calls_operation", table_name="agent_model_calls")
    op.drop_index("ix_agent_model_calls_owner_id", table_name="agent_model_calls")
    op.drop_table("agent_model_calls")
