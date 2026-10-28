"""Ensure the structured interview state columns exist on every runtime database."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8e1f4c62a30"
down_revision: str | Sequence[str] | None = "a1c2d3e4f567"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    session_columns = {item["name"] for item in inspector.get_columns("interview_sessions")}
    additions = [
        ("interview_type", sa.String(30), "standard"),
        ("question_plan_json", sa.Text(), "[]"),
        ("current_core_index", sa.Integer(), "0"),
        ("current_question_kind", sa.String(20), "core"),
        ("follow_up_count", sa.Integer(), "0"),
        ("total_turns", sa.Integer(), "0"),
        ("max_follow_ups", sa.Integer(), "2"),
        ("core_question_count", sa.Integer(), "6"),
        ("rubric_version", sa.String(40), "interview-v1"),
        ("rubric_json", sa.Text(), "[]"),
        ("final_report_json", sa.Text(), None),
        ("completed_at", sa.DateTime(timezone=True), None),
    ]
    for name, column_type, default in additions:
        if name in session_columns:
            continue
        column = sa.Column(
            name,
            column_type,
            nullable=name in {"final_report_json", "completed_at"},
        )
        if default is not None:
            column.server_default = sa.text(repr(default))
        op.add_column("interview_sessions", column)

    turn_columns = {item["name"] for item in inspector.get_columns("interview_turns")}
    if "assistant_content" not in turn_columns:
        op.add_column("interview_turns", sa.Column("assistant_content", sa.Text(), nullable=True))


def downgrade() -> None:
    # The columns are shared with older compatibility revisions; keep downgrade non-destructive.
    pass
