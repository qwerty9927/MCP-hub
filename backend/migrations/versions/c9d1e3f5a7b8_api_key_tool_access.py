"""api_key_tool_access

Revision ID: c9d1e3f5a7b8
Revises: b8c0d2e4f6a7
Create Date: 2026-11-16 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9d1e3f5a7b8"
down_revision: str | Sequence[str] | None = "b8c0d2e4f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Tools hidden from one API key (ADR-0007). No rows means every key sees every tool, as before."""
    op.create_table(
        "api_key_disabled_tools",
        sa.Column("api_key_id", sa.String(length=36), sa.ForeignKey("api_keys.id", ondelete="CASCADE"), nullable=False),
        sa.Column("server_id", sa.String(length=36), sa.ForeignKey("mcp_servers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tool_name", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("api_key_id", "server_id", "tool_name", name="pk_api_key_disabled_tools"),
    )


def downgrade() -> None:
    op.drop_table("api_key_disabled_tools")
