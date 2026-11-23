"""console_refresh_tokens

Revision ID: b8d0f2a4c6e9
Revises: a3c5e7f9b1d4
Create Date: 2026-11-23 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8d0f2a4c6e9"
down_revision: str | Sequence[str] | None = "a3c5e7f9b1d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Console refresh tokens (ADR-0009): hashes only, grouped by sign-in (family) so reuse revokes the family."""
    op.create_table(
        "console_refresh_tokens",
        sa.Column("id", sa.String(length=36), server_default=sa.text("gen_random_uuid()::text"), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("family_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_console_refresh_tokens_user_id"), "console_refresh_tokens", ["user_id"], unique=False)
    op.create_index(op.f("ix_console_refresh_tokens_family_id"), "console_refresh_tokens", ["family_id"], unique=False)
    op.create_index(op.f("ix_console_refresh_tokens_token_hash"), "console_refresh_tokens", ["token_hash"], unique=True)
    op.create_index(op.f("ix_console_refresh_tokens_expires_at"), "console_refresh_tokens", ["expires_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_console_refresh_tokens_expires_at"), table_name="console_refresh_tokens")
    op.drop_index(op.f("ix_console_refresh_tokens_token_hash"), table_name="console_refresh_tokens")
    op.drop_index(op.f("ix_console_refresh_tokens_family_id"), table_name="console_refresh_tokens")
    op.drop_index(op.f("ix_console_refresh_tokens_user_id"), table_name="console_refresh_tokens")
    op.drop_table("console_refresh_tokens")
