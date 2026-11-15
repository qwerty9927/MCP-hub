"""add_ownership

Revision ID: d4e6b8c0f2a3
Revises: c3d5a7b9e1f2
Create Date: 2026-11-12 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e6b8c0f2a3"
down_revision: str | Sequence[str] | None = "c3d5a7b9e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Scope servers, tools and sessions to an owning account. Existing rows stay unowned; a later revision (f6a8b0d2c4e5) deletes them and requires an owner."""
    op.add_column("mcp_servers", sa.Column("owner_id", sa.String(length=36), nullable=True))
    op.create_foreign_key("fk_mcp_servers_owner_id", "mcp_servers", "users", ["owner_id"], ["id"], ondelete="CASCADE")
    op.create_index(op.f("ix_mcp_servers_owner_id"), "mcp_servers", ["owner_id"], unique=False)
    op.drop_index(op.f("ix_mcp_servers_name"), table_name="mcp_servers")
    op.create_index(op.f("ix_mcp_servers_name"), "mcp_servers", ["name"], unique=False)
    op.create_unique_constraint("uq_mcp_servers_owner_name", "mcp_servers", ["owner_id", "name"])

    op.add_column("discovered_tools", sa.Column("owner_id", sa.String(length=36), nullable=True))
    op.create_index(op.f("ix_discovered_tools_owner_id"), "discovered_tools", ["owner_id"], unique=False)

    op.add_column("mcp_sessions", sa.Column("owner_id", sa.String(length=36), nullable=True))
    op.add_column("mcp_sessions", sa.Column("api_key_id", sa.String(length=36), nullable=True))
    op.add_column("mcp_sessions", sa.Column("client_fingerprint", sa.String(length=64), nullable=True))
    op.create_foreign_key("fk_mcp_sessions_owner_id", "mcp_sessions", "users", ["owner_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key("fk_mcp_sessions_api_key_id", "mcp_sessions", "api_keys", ["api_key_id"], ["id"], ondelete="SET NULL")
    op.create_index(op.f("ix_mcp_sessions_owner_id"), "mcp_sessions", ["owner_id"], unique=False)
    op.create_index(
        "ix_mcp_sessions_owner_fingerprint_activity",
        "mcp_sessions",
        ["owner_id", "client_fingerprint", "last_activity_at"],
        unique=False,
    )


def downgrade() -> None:
    """Remove ownership columns (restoring the globally unique server name needs no duplicate names)."""
    op.drop_index("ix_mcp_sessions_owner_fingerprint_activity", table_name="mcp_sessions")
    op.drop_index(op.f("ix_mcp_sessions_owner_id"), table_name="mcp_sessions")
    op.drop_constraint("fk_mcp_sessions_api_key_id", "mcp_sessions", type_="foreignkey")
    op.drop_constraint("fk_mcp_sessions_owner_id", "mcp_sessions", type_="foreignkey")
    op.drop_column("mcp_sessions", "client_fingerprint")
    op.drop_column("mcp_sessions", "api_key_id")
    op.drop_column("mcp_sessions", "owner_id")

    op.drop_index(op.f("ix_discovered_tools_owner_id"), table_name="discovered_tools")
    op.drop_column("discovered_tools", "owner_id")

    op.drop_constraint("uq_mcp_servers_owner_name", "mcp_servers", type_="unique")
    op.drop_index(op.f("ix_mcp_servers_name"), table_name="mcp_servers")
    op.create_index(op.f("ix_mcp_servers_name"), "mcp_servers", ["name"], unique=True)
    op.drop_index(op.f("ix_mcp_servers_owner_id"), table_name="mcp_servers")
    op.drop_constraint("fk_mcp_servers_owner_id", "mcp_servers", type_="foreignkey")
    op.drop_column("mcp_servers", "owner_id")
