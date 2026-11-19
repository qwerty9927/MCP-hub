"""oauth_credentials_user_id

Revision ID: f2a4b6c8d0e3
Revises: e1f3a5b7c9d2
Create Date: 2026-11-19 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2a4b6c8d0e3"
down_revision: str | Sequence[str] | None = "e1f3a5b7c9d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """OAuth credentials carry their owner (a copy of the server's), so lookups are scoped without a join."""
    op.add_column("server_oauth_credentials", sa.Column("user_id", sa.String(length=36), nullable=True))
    op.execute("UPDATE server_oauth_credentials c SET user_id = s.user_id FROM mcp_servers s WHERE s.id = c.server_id")
    op.alter_column("server_oauth_credentials", "user_id", nullable=False)
    op.create_foreign_key(
        "server_oauth_credentials_user_id_fkey", "server_oauth_credentials", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index("ix_server_oauth_credentials_user_id", "server_oauth_credentials", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_server_oauth_credentials_user_id", table_name="server_oauth_credentials")
    op.drop_constraint("server_oauth_credentials_user_id_fkey", "server_oauth_credentials", type_="foreignkey")
    op.drop_column("server_oauth_credentials", "user_id")
