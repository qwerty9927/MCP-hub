"""add_response_to_tool_executions

Revision ID: eaf91cf5f7f5
Revises: b42f22ff6450
Create Date: 2026-11-07 10:49:26.520376

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "eaf91cf5f7f5"
down_revision: str | Sequence[str] | None = "b42f22ff6450"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("tool_executions", sa.Column("response", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("tool_executions", "response")
