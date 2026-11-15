"""uniform_uuid_ids

Revision ID: a7b9c1d3e5f6
Revises: f6a8b0d2c4e5
Create Date: 2026-11-15 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7b9c1d3e5f6"
down_revision: str | Sequence[str] | None = "f6a8b0d2c4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_UUID_DEFAULT = sa.text("gen_random_uuid()::text")
_ID_TABLES = ("users", "api_keys", "mcp_servers", "discovered_tools", "mcp_sessions", "tool_executions")


def upgrade() -> None:
    """Every id is a `str(UUID)` in varchar(36), with `gen_random_uuid()` as the database default.

    Sessions used to be `uuid4().hex` and Tools `"{server_id}:{tool_name}"`. Their old rows are deleted, not
    converted: Tools come back on the next connect, and past Sessions and Executions are dropped.
    """
    op.execute("DELETE FROM tool_executions")
    op.execute("DELETE FROM mcp_sessions")
    op.execute("DELETE FROM discovered_tools")

    op.alter_column("mcp_sessions", "id", type_=sa.String(length=36), existing_type=sa.String(length=64))
    op.alter_column("tool_executions", "session_id", type_=sa.String(length=36), existing_type=sa.String(length=64))
    op.alter_column("discovered_tools", "id", type_=sa.String(length=36), existing_type=sa.String(length=140))
    op.create_unique_constraint("uq_discovered_tools_server_name", "discovered_tools", ["server_id", "name"])

    for table in _ID_TABLES:
        op.alter_column(table, "id", server_default=_UUID_DEFAULT, existing_type=sa.String(length=36))


def downgrade() -> None:
    """Back to the old column sizes, with no database default. Deleted rows are not restored."""
    for table in _ID_TABLES:
        op.alter_column(table, "id", server_default=None, existing_type=sa.String(length=36))

    op.drop_constraint("uq_discovered_tools_server_name", "discovered_tools", type_="unique")
    op.alter_column("discovered_tools", "id", type_=sa.String(length=140), existing_type=sa.String(length=36))
    op.alter_column("tool_executions", "session_id", type_=sa.String(length=64), existing_type=sa.String(length=36))
    op.alter_column("mcp_sessions", "id", type_=sa.String(length=64), existing_type=sa.String(length=36))
