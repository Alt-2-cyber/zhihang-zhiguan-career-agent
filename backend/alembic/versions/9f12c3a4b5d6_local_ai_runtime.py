"""local ai runtime

Revision ID: 9f12c3a4b5d6
Revises: 75bc1841affe
Create Date: 2026-07-14 18:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "9f12c3a4b5d6"
down_revision: str | Sequence[str] | None = "e7c4d5f601a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    if {"ai_tasks", "document_chunks", "media_artifacts"}.issubset(existing):
        return
    if op.get_bind().dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "ai_tasks",
        sa.Column("task_type", sa.String(length=40), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("input_json", sa.Text(), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.String(length=300), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_tasks_task_type", "ai_tasks", ["task_type"])
    op.create_index("ix_ai_tasks_owner_id", "ai_tasks", ["owner_id"])
    op.create_index("ix_ai_tasks_status", "ai_tasks", ["status"])
    op.create_index("ix_ai_tasks_available_at", "ai_tasks", ["available_at"])
    op.create_index("ix_ai_tasks_lease_expires_at", "ai_tasks", ["lease_expires_at"])

    vector_type = Vector(1024) if op.get_bind().dialect.name == "postgresql" else sa.JSON()
    op.create_table(
        "document_chunks",
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding", vector_type, nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_type", "source_id", "chunk_index", name="uq_document_chunk"),
    )
    op.create_index("ix_document_chunks_source_type", "document_chunks", ["source_type"])
    op.create_index("ix_document_chunks_source_id", "document_chunks", ["source_id"])
    op.create_index("ix_document_chunks_owner_id", "document_chunks", ["owner_id"])
    op.create_index("ix_document_chunks_content_hash", "document_chunks", ["content_hash"])

    op.create_table(
        "media_artifacts",
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=True),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("media_type", sa.String(length=120), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["session_id"], ["interview_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_path"),
    )
    op.create_index("ix_media_artifacts_owner_id", "media_artifacts", ["owner_id"])
    op.create_index("ix_media_artifacts_session_id", "media_artifacts", ["session_id"])
    op.create_index("ix_media_artifacts_kind", "media_artifacts", ["kind"])
    op.create_index("ix_media_artifacts_expires_at", "media_artifacts", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_media_artifacts_expires_at", table_name="media_artifacts")
    op.drop_index("ix_media_artifacts_kind", table_name="media_artifacts")
    op.drop_index("ix_media_artifacts_session_id", table_name="media_artifacts")
    op.drop_index("ix_media_artifacts_owner_id", table_name="media_artifacts")
    op.drop_table("media_artifacts")
    op.drop_index("ix_document_chunks_content_hash", table_name="document_chunks")
    op.drop_index("ix_document_chunks_owner_id", table_name="document_chunks")
    op.drop_index("ix_document_chunks_source_id", table_name="document_chunks")
    op.drop_index("ix_document_chunks_source_type", table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_index("ix_ai_tasks_lease_expires_at", table_name="ai_tasks")
    op.drop_index("ix_ai_tasks_available_at", table_name="ai_tasks")
    op.drop_index("ix_ai_tasks_status", table_name="ai_tasks")
    op.drop_index("ix_ai_tasks_owner_id", table_name="ai_tasks")
    op.drop_index("ix_ai_tasks_task_type", table_name="ai_tasks")
    op.drop_table("ai_tasks")
