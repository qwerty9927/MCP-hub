"""keep_executions_after_server_delete

Revision ID: e1f3a5b7c9d2
Revises: d0e2f4a6b8c1
Create Date: 2026-11-17 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1f3a5b7c9d2"
down_revision: str | Sequence[str] | None = "d0e2f4a6b8c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Executions outlive their Server: the owner is stored on the Execution, and server_id keeps the deleted
    Server's id (no foreign key)."""
    op.add_column("tool_executions", sa.Column("user_id", sa.String(length=36), nullable=True))
    op.execute("UPDATE tool_executions e SET user_id = s.user_id FROM mcp_servers s WHERE s.id = e.server_id")
    op.alter_column("tool_executions", "user_id", nullable=False)
    op.create_foreign_key("tool_executions_user_id_fkey", "tool_executions", "users", ["user_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_tool_executions_user_id", "tool_executions", ["user_id"])

    op.drop_constraint("tool_executions_server_id_fkey", "tool_executions", type_="foreignkey")


def downgrade() -> None:
    # Executions of deleted Servers cannot satisfy the foreign key again; they are removed, as CASCADE would have done.
    op.execute("DELETE FROM tool_executions e WHERE NOT EXISTS (SELECT 1 FROM mcp_servers s WHERE s.id = e.server_id)")
    op.create_foreign_key("tool_executions_server_id_fkey", "tool_executions", "mcp_servers", ["server_id"], ["id"], ondelete="CASCADE")
    op.drop_index("ix_tool_executions_user_id", table_name="tool_executions")
    op.drop_constraint("tool_executions_user_id_fkey", "tool_executions", type_="foreignkey")
    op.drop_column("tool_executions", "user_id")
