"""add_session_idle_timeout

Revision ID: e5f7a9c1b3d4
Revises: d4e6b8c0f2a3
Create Date: 2026-11-15 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f7a9c1b3d4"
down_revision: str | Sequence[str] | None = "d4e6b8c0f2a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Per-API-key Session idle timeout, its per-Session snapshot, and an index for the job that completes idle Sessions."""
    op.add_column("api_keys", sa.Column("session_idle_minutes", sa.Integer(), nullable=True))
    op.add_column("mcp_sessions", sa.Column("idle_timeout_seconds", sa.Integer(), nullable=True))
    op.create_index("ix_mcp_sessions_status_activity", "mcp_sessions", ["status", "last_activity_at"], unique=False)


def downgrade() -> None:
    """Drop the Session idle timeout columns and the sweep index."""
    op.drop_index("ix_mcp_sessions_status_activity", table_name="mcp_sessions")
    op.drop_column("mcp_sessions", "idle_timeout_seconds")
    op.drop_column("api_keys", "session_idle_minutes")
