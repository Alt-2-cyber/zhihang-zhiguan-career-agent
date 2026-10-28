"""Add structured post-hire work context and deliverables.

Revision ID: 4f6a7b8c9d01
Revises: c1d2e3f4a5b6
Create Date: 2026-08-07
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "4f6a7b8c9d01"
down_revision: str | Sequence[str] | None = "c1d2e3f4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())

    if "simulation_scenarios" not in tables:
        op.create_table(
            "simulation_scenarios",
            sa.Column("title", sa.String(160), nullable=False),
            sa.Column("category", sa.String(60), nullable=False),
            sa.Column("difficulty", sa.String(20), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("competencies_json", sa.Text(), nullable=False),
            sa.Column("steps_json", sa.Text(), nullable=False),
            sa.Column("rubric_json", sa.Text(), nullable=False),
            sa.Column("mode", sa.String(30), nullable=False),
            sa.Column("stage_definition_json", sa.Text(), nullable=False),
            sa.Column("safety_policy_json", sa.Text(), nullable=False),
            sa.Column("status", sa.String(30), nullable=False),
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        tables.add("simulation_scenarios")

    if "simulation_sessions" not in tables:
        op.create_table(
            "simulation_sessions",
            sa.Column("student_id", sa.String(36), nullable=False),
            sa.Column("scenario_id", sa.String(36), nullable=False),
            sa.Column("status", sa.String(30), nullable=False),
            sa.Column("mode", sa.String(30), nullable=False),
            sa.Column("stage", sa.String(60), nullable=False),
            sa.Column("stress_level", sa.String(20), nullable=False),
            sa.Column("current_step", sa.Integer(), nullable=False),
            sa.Column("score", sa.Integer(), nullable=True),
            sa.Column("assessment_json", sa.Text(), nullable=True),
            sa.Column("report_json", sa.Text(), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint(
                "score IS NULL OR (score BETWEEN 0 AND 100)",
                name="ck_simulation_session_score",
            ),
            sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["scenario_id"], ["simulation_scenarios.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        tables.add("simulation_sessions")

    if "simulation_turns" not in tables:
        op.create_table(
            "simulation_turns",
            sa.Column("session_id", sa.String(36), nullable=False),
            sa.Column("student_id", sa.String(36), nullable=False),
            sa.Column("sequence", sa.Integer(), nullable=False),
            sa.Column("prompt", sa.Text(), nullable=False),
            sa.Column("response", sa.Text(), nullable=False),
            sa.Column("score", sa.Integer(), nullable=False),
            sa.Column("feedback_json", sa.Text(), nullable=False),
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("score BETWEEN 0 AND 100", name="ck_simulation_turn_score"),
            sa.ForeignKeyConstraint(["session_id"], ["simulation_sessions.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("session_id", "sequence", name="uq_simulation_turn_sequence"),
        )
        tables.add("simulation_turns")

    if "simulation_material_bindings" not in tables:
        op.create_table(
            "simulation_material_bindings",
            sa.Column("session_id", sa.String(36), nullable=False),
            sa.Column("student_id", sa.String(36), nullable=False),
            sa.Column("source_type", sa.String(30), nullable=False),
            sa.Column("source_id", sa.String(36), nullable=False),
            sa.Column("purpose", sa.String(60), nullable=False),
            sa.Column("context_preview", sa.Text(), nullable=True),
            sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["session_id"], ["simulation_sessions.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "session_id", "source_type", "source_id", "purpose",
                name="uq_simulation_material_binding",
            ),
        )
        tables.add("simulation_material_bindings")

    if "simulation_messages" not in tables:
        op.create_table(
            "simulation_messages",
            sa.Column("session_id", sa.String(36), nullable=False),
            sa.Column("sequence", sa.Integer(), nullable=False),
            sa.Column("speaker", sa.String(60), nullable=False),
            sa.Column("display_name", sa.String(80), nullable=False),
            sa.Column("stage", sa.String(60), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("reply_to", sa.String(36), nullable=True),
            sa.Column("metadata_json", sa.Text(), nullable=False),
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["session_id"], ["simulation_sessions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("session_id", "sequence", name="uq_simulation_message_sequence"),
        )
        tables.add("simulation_messages")

    scenario_columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("simulation_scenarios")
    }
    if "work_context_json" not in scenario_columns:
        op.add_column(
            "simulation_scenarios",
            sa.Column("work_context_json", sa.Text(), nullable=False, server_default="{}"),
        )

    if "workplace_deliverables" not in tables:
        op.create_table(
            "workplace_deliverables",
            sa.Column("session_id", sa.String(length=36), nullable=False),
            sa.Column("student_id", sa.String(length=36), nullable=False),
            sa.Column("action_type", sa.String(length=40), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("revision", sa.Integer(), nullable=False),
            sa.Column("reviewer_feedback", sa.Text(), nullable=True),
            sa.Column("review_json", sa.Text(), nullable=True),
            sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint(
                "status IN ('draft', 'submitted', 'reviewed')",
                name="ck_workplace_deliverable_status",
            ),
            sa.CheckConstraint("revision >= 1", name="ck_workplace_deliverable_revision"),
            sa.ForeignKeyConstraint(
                ["session_id"], ["simulation_sessions.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "session_id", "action_type", "revision", name="uq_workplace_deliverable_revision"
            ),
        )
        tables.add("workplace_deliverables")

    indexes = {
        "simulation_scenarios": ["title", "category", "difficulty", "mode", "status"],
        "simulation_sessions": ["student_id", "scenario_id", "status", "mode", "stage"],
        "simulation_turns": ["session_id", "student_id"],
        "simulation_material_bindings": ["session_id", "student_id", "source_id"],
        "simulation_messages": ["speaker", "stage"],
        "workplace_deliverables": ["session_id", "student_id", "action_type", "status"],
    }
    for table_name, columns in indexes.items():
        existing_indexes = {
            item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table_name)
        }
        for column_name in columns:
            index_name = f"ix_{table_name}_{column_name}"
            if index_name not in existing_indexes:
                op.create_index(index_name, table_name, [column_name])

    composite_indexes = {
        "ix_simulation_session_student_status_updated": (
            "simulation_sessions", ["student_id", "status", "updated_at"]
        ),
        "ix_simulation_material_student_created": (
            "simulation_material_bindings", ["student_id", "created_at"]
        ),
        "ix_simulation_message_session_created": (
            "simulation_messages", ["session_id", "created_at"]
        ),
        "ix_workplace_deliverable_student_status": (
            "workplace_deliverables", ["student_id", "status"]
        ),
        "ix_workplace_deliverable_session_updated": (
            "workplace_deliverables", ["session_id", "updated_at"]
        ),
    }
    for index_name, (table_name, columns) in composite_indexes.items():
        existing_indexes = {
            item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table_name)
        }
        if index_name not in existing_indexes:
            op.create_index(index_name, table_name, columns)


def downgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "workplace_deliverables" in tables:
        for index_name in (
            "ix_workplace_deliverable_session_updated",
            "ix_workplace_deliverable_student_status",
            "ix_workplace_deliverables_status",
            "ix_workplace_deliverables_action_type",
            "ix_workplace_deliverables_student_id",
            "ix_workplace_deliverables_session_id",
        ):
            indexes = {
                item["name"]
                for item in sa.inspect(op.get_bind()).get_indexes("workplace_deliverables")
            }
            if index_name in indexes:
                op.drop_index(index_name, table_name="workplace_deliverables")
        op.drop_table("workplace_deliverables")
    if "simulation_scenarios" in tables:
        columns = {
            column["name"]
            for column in sa.inspect(op.get_bind()).get_columns("simulation_scenarios")
        }
        if "work_context_json" in columns:
            op.drop_column("simulation_scenarios", "work_context_json")
