"""add_mcp_sessions_and_execution_fields

Revision ID: 8f2c3b1a9e4d
Revises: eaf91cf5f7f5
Create Date: 2026-11-08 10:50:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8f2c3b1a9e4d"
down_revision: str | Sequence[str] | None = "eaf91cf5f7f5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema to support MCP Sessions and execution tracking."""
    # 1. Create mcp_sessions table
    op.create_table(
        "mcp_sessions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_mcp_sessions_title"), "mcp_sessions", ["title"], unique=False)
    op.create_index(op.f("ix_mcp_sessions_status"), "mcp_sessions", ["status"], unique=False)
    op.create_index(
        op.f("ix_mcp_sessions_last_activity_at"),
        "mcp_sessions",
        ["last_activity_at"],
        unique=False,
    )

    # 2. Add session tracking columns and constraints to tool_executions
    op.add_column("tool_executions", sa.Column("session_id", sa.String(length=64), nullable=True))
    op.add_column(
        "tool_executions",
        sa.Column("status", sa.String(length=20), server_default="completed", nullable=False),
    )
    op.add_column(
        "tool_executions",
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tool_executions",
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_foreign_key(
        "fk_tool_executions_session_id",
        "tool_executions",
        "mcp_sessions",
        ["session_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        op.f("ix_tool_executions_session_id"), "tool_executions", ["session_id"], unique=False
    )
    op.create_index(op.f("ix_tool_executions_status"), "tool_executions", ["status"], unique=False)
    op.create_index(
        op.f("ix_tool_executions_session_started_at"),
        "tool_executions",
        ["session_id", "started_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tool_executions_session_status"),
        "tool_executions",
        ["session_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_tool_executions_session_status"), table_name="tool_executions")
    op.drop_index(op.f("ix_tool_executions_session_started_at"), table_name="tool_executions")
    op.drop_index(op.f("ix_tool_executions_status"), table_name="tool_executions")
    op.drop_index(op.f("ix_tool_executions_session_id"), table_name="tool_executions")
    op.drop_constraint("fk_tool_executions_session_id", "tool_executions", type_="foreignkey")

    op.drop_column("tool_executions", "completed_at")
    op.drop_column("tool_executions", "started_at")
    op.drop_column("tool_executions", "status")
    op.drop_column("tool_executions", "session_id")

    op.drop_index(op.f("ix_mcp_sessions_last_activity_at"), table_name="mcp_sessions")
    op.drop_index(op.f("ix_mcp_sessions_status"), table_name="mcp_sessions")
    op.drop_index(op.f("ix_mcp_sessions_title"), table_name="mcp_sessions")
    op.drop_table("mcp_sessions")
