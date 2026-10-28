"""conversational agent state

Revision ID: c7a91d2e4f60
Revises: 9f12c3a4b5d6
Create Date: 2026-07-15 02:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c7a91d2e4f60"
down_revision: str | Sequence[str] | None = "9f12c3a4b5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def entity_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    required = {
        "chat_sessions",
        "chat_messages",
        "chat_attachments",
        "agent_runs",
        "agent_steps",
        "tool_calls",
        "action_proposals",
        "agent_events",
    }
    if required.issubset(existing):
        return
    op.create_table(
        "chat_sessions",
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("subject_student_id", sa.String(length=36), nullable=True),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("summary_source_ids_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        *entity_columns(),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_student_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_sessions_owner_id", "chat_sessions", ["owner_id"])
    op.create_index(
        "ix_chat_sessions_subject_student_id", "chat_sessions", ["subject_student_id"]
    )
    op.create_index("ix_chat_sessions_role", "chat_sessions", ["role"])
    op.create_index("ix_chat_sessions_status", "chat_sessions", ["status"])

    op.create_table(
        "chat_messages",
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("sender", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("attachment_ids_json", sa.Text(), nullable=False),
        sa.Column("citations_json", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=True),
        sa.Column("request_key", sa.String(length=120), nullable=True),
        *entity_columns(),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "request_key", name="uq_chat_message_request"),
    )
    op.create_index("ix_chat_messages_session_id", "chat_messages", ["session_id"])
    op.create_index("ix_chat_messages_sender", "chat_messages", ["sender"])

    op.create_table(
        "chat_attachments",
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("media_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("parse_status", sa.String(length=30), nullable=False),
        sa.Column("parse_error", sa.String(length=300), nullable=True),
        sa.Column("parsed_text", sa.Text(), nullable=True),
        sa.Column("ai_task_id", sa.String(length=36), nullable=True),
        *entity_columns(),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ai_task_id"], ["ai_tasks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_path"),
    )
    op.create_index("ix_chat_attachments_session_id", "chat_attachments", ["session_id"])
    op.create_index("ix_chat_attachments_owner_id", "chat_attachments", ["owner_id"])
    op.create_index("ix_chat_attachments_parse_status", "chat_attachments", ["parse_status"])
    op.create_index("ix_chat_attachments_ai_task_id", "chat_attachments", ["ai_task_id"])

    op.create_table(
        "agent_runs",
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("user_message_id", sa.String(length=36), nullable=False),
        sa.Column("assistant_message_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("plan_json", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("tool_call_count", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.String(length=300), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *entity_columns(),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_message_id"], ["chat_messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["assistant_message_id"], ["chat_messages.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_message_id"),
        sa.UniqueConstraint("assistant_message_id"),
    )
    op.create_index("ix_agent_runs_session_id", "agent_runs", ["session_id"])
    op.create_index("ix_agent_runs_status", "agent_runs", ["status"])

    op.create_table(
        "agent_steps",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("step_key", sa.String(length=40), nullable=False),
        sa.Column("agent_name", sa.String(length=40), nullable=False),
        sa.Column("instruction", sa.String(length=500), nullable=False),
        sa.Column("dependencies_json", sa.Text(), nullable=False),
        sa.Column("input_json", sa.Text(), nullable=False),
        sa.Column("output_json", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.String(length=300), nullable=True),
        *entity_columns(),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "step_key", name="uq_agent_step_key"),
    )
    op.create_index("ix_agent_steps_run_id", "agent_steps", ["run_id"])
    op.create_index("ix_agent_steps_agent_name", "agent_steps", ["agent_name"])
    op.create_index("ix_agent_steps_status", "agent_steps", ["status"])

    op.create_table(
        "tool_calls",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("step_id", sa.String(length=36), nullable=True),
        sa.Column("tool_name", sa.String(length=80), nullable=False),
        sa.Column("tool_version", sa.String(length=20), nullable=False),
        sa.Column("arguments_json", sa.Text(), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("risk", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.String(length=300), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *entity_columns(),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["step_id"], ["agent_steps.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_tool_calls_run_id", "tool_calls", ["run_id"])
    op.create_index("ix_tool_calls_step_id", "tool_calls", ["step_id"])
    op.create_index("ix_tool_calls_tool_name", "tool_calls", ["tool_name"])
    op.create_index("ix_tool_calls_risk", "tool_calls", ["risk"])
    op.create_index("ix_tool_calls_status", "tool_calls", ["status"])

    op.create_table(
        "action_proposals",
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("tool_call_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("risk", sa.String(length=30), nullable=False),
        sa.Column("arguments_json", sa.Text(), nullable=False),
        sa.Column("preview_json", sa.Text(), nullable=False),
        sa.Column("undo_json", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("decided_by", sa.String(length=36), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        *entity_columns(),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tool_call_id"], ["tool_calls.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["decided_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tool_call_id"),
    )
    op.create_index("ix_action_proposals_session_id", "action_proposals", ["session_id"])
    op.create_index("ix_action_proposals_run_id", "action_proposals", ["run_id"])
    op.create_index("ix_action_proposals_risk", "action_proposals", ["risk"])
    op.create_index("ix_action_proposals_status", "action_proposals", ["status"])
    op.create_index("ix_action_proposals_expires_at", "action_proposals", ["expires_at"])

    op.create_table(
        "agent_events",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        *entity_columns(),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "sequence", name="uq_agent_event_sequence"),
    )
    op.create_index("ix_agent_events_run_id", "agent_events", ["run_id"])
    op.create_index("ix_agent_events_event_type", "agent_events", ["event_type"])

    with op.batch_alter_table("media_artifacts") as batch_op:
        batch_op.add_column(sa.Column("chat_session_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_media_artifacts_chat_session_id_chat_sessions",
            "chat_sessions",
            ["chat_session_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_index("ix_media_artifacts_chat_session_id", ["chat_session_id"])

    with op.batch_alter_table("jobs") as batch_op:
        batch_op.add_column(sa.Column("source_url", sa.String(length=1000), nullable=True))
        batch_op.add_column(sa.Column("source_kind", sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column("source_fetched_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(
            sa.Column("status", sa.String(length=30), nullable=False, server_default="active")
        )
        batch_op.create_index("ix_jobs_source_kind", ["source_kind"])
        batch_op.create_index("ix_jobs_status", ["status"])


def downgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.drop_index("ix_jobs_status")
        batch_op.drop_index("ix_jobs_source_kind")
        batch_op.drop_column("status")
        batch_op.drop_column("source_fetched_at")
        batch_op.drop_column("source_kind")
        batch_op.drop_column("source_url")

    with op.batch_alter_table("media_artifacts") as batch_op:
        batch_op.drop_index("ix_media_artifacts_chat_session_id")
        batch_op.drop_constraint(
            "fk_media_artifacts_chat_session_id_chat_sessions", type_="foreignkey"
        )
        batch_op.drop_column("chat_session_id")

    op.drop_index("ix_agent_events_event_type", table_name="agent_events")
    op.drop_index("ix_agent_events_run_id", table_name="agent_events")
    op.drop_table("agent_events")
    op.drop_index("ix_action_proposals_expires_at", table_name="action_proposals")
    op.drop_index("ix_action_proposals_status", table_name="action_proposals")
    op.drop_index("ix_action_proposals_risk", table_name="action_proposals")
    op.drop_index("ix_action_proposals_run_id", table_name="action_proposals")
    op.drop_index("ix_action_proposals_session_id", table_name="action_proposals")
    op.drop_table("action_proposals")
    op.drop_index("ix_tool_calls_status", table_name="tool_calls")
    op.drop_index("ix_tool_calls_risk", table_name="tool_calls")
    op.drop_index("ix_tool_calls_tool_name", table_name="tool_calls")
    op.drop_index("ix_tool_calls_step_id", table_name="tool_calls")
    op.drop_index("ix_tool_calls_run_id", table_name="tool_calls")
    op.drop_table("tool_calls")
    op.drop_index("ix_agent_steps_status", table_name="agent_steps")
    op.drop_index("ix_agent_steps_agent_name", table_name="agent_steps")
    op.drop_index("ix_agent_steps_run_id", table_name="agent_steps")
    op.drop_table("agent_steps")
    op.drop_index("ix_agent_runs_status", table_name="agent_runs")
    op.drop_index("ix_agent_runs_session_id", table_name="agent_runs")
    op.drop_table("agent_runs")
    op.drop_index("ix_chat_attachments_ai_task_id", table_name="chat_attachments")
    op.drop_index("ix_chat_attachments_parse_status", table_name="chat_attachments")
    op.drop_index("ix_chat_attachments_owner_id", table_name="chat_attachments")
    op.drop_index("ix_chat_attachments_session_id", table_name="chat_attachments")
    op.drop_table("chat_attachments")
    op.drop_index("ix_chat_messages_sender", table_name="chat_messages")
    op.drop_index("ix_chat_messages_session_id", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_sessions_status", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_role", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_subject_student_id", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_owner_id", table_name="chat_sessions")
    op.drop_table("chat_sessions")
