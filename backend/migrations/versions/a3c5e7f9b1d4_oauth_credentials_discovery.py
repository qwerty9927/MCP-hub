"""oauth_credentials_discovery

Revision ID: a3c5e7f9b1d4
Revises: f2a4b6c8d0e3
Create Date: 2026-11-23 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3c5e7f9b1d4"
down_revision: str | Sequence[str] | None = "f2a4b6c8d0e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Keep the authorization server metadata found at sign-in, so later sessions refresh tokens at the real token
    endpoint. Existing rows stay empty and are filled the first time the hub connects them."""
    op.add_column("server_oauth_credentials", sa.Column("discovery_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("server_oauth_credentials", "discovery_json")
