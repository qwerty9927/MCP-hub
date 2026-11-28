"""auth_rate_limits

Revision ID: c1e3a5b7d9f2
Revises: b8d0f2a4c6e9
Create Date: 2026-11-28 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1e3a5b7d9f2"
down_revision: str | Sequence[str] | None = "b8d0f2a4c6e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Attempt counters for /auth/login, /register and /refresh, shared by every hub instance."""
    op.create_table(
        "auth_rate_limits",
        sa.Column("bucket_key", sa.String(length=320), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("bucket_key"),
    )
    op.create_index(op.f("ix_auth_rate_limits_window_started_at"), "auth_rate_limits", ["window_started_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_auth_rate_limits_window_started_at"), table_name="auth_rate_limits")
    op.drop_table("auth_rate_limits")
