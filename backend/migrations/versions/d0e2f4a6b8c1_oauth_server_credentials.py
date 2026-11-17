"""oauth_server_credentials

Revision ID: d0e2f4a6b8c1
Revises: c9d1e3f5a7b8
Create Date: 2026-11-17 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d0e2f4a6b8c1"
down_revision: str | Sequence[str] | None = "c9d1e3f5a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Servers connected with OAuth (ADR-0008): how a server authenticates, and its encrypted credentials."""
    op.add_column("mcp_servers", sa.Column("auth_type", sa.String(length=20), nullable=False, server_default="none"))
    op.add_column("mcp_servers", sa.Column("oauth_provider_id", sa.String(length=50), nullable=True))
    op.create_table(
        "server_oauth_credentials",
        sa.Column("server_id", sa.String(length=36), sa.ForeignKey("mcp_servers.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("client_info_enc", sa.Text(), nullable=True),
        sa.Column("tokens_enc", sa.Text(), nullable=True),
        sa.Column("access_token_expires_at", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("server_oauth_credentials")
    op.drop_column("mcp_servers", "oauth_provider_id")
    op.drop_column("mcp_servers", "auth_type")
