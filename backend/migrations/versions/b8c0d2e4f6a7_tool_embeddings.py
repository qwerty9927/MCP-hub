"""tool_embeddings

Revision ID: b8c0d2e4f6a7
Revises: a7b9c1d3e5f6
Create Date: 2026-11-16 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "b8c0d2e4f6a7"
down_revision: str | Sequence[str] | None = "a7b9c1d3e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Fixed here, not read from settings: a migration must not change meaning when .env changes.
# A different EMBEDDING_DIMENSION needs a new migration that resizes the column.
_DIMENSION = 384


def upgrade() -> None:
    """SEARCH_TOOLS ranks Tools by cosine similarity in pgvector (ADR-0006).

    Existing Tools get NULL embeddings; the hub fills them in at startup and on a schedule.
    """
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column("discovered_tools", sa.Column("embedding", Vector(_DIMENSION), nullable=True))
    op.create_index(
        "ix_discovered_tools_embedding",
        "discovered_tools",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    """Drop the column and index. The extension stays: other schemas may use it."""
    op.drop_index("ix_discovered_tools_embedding", table_name="discovered_tools")
    op.drop_column("discovered_tools", "embedding")
