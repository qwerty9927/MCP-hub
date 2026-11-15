"""rename_owner_id_to_user_id

Revision ID: f6a8b0d2c4e5
Revises: e5f7a9c1b3d4
Create Date: 2026-11-15 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6a8b0d2c4e5"
down_revision: str | Sequence[str] | None = "e5f7a9c1b3d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("mcp_servers", "discovered_tools", "mcp_sessions")

# (old name, new name) for every index and constraint that carried "owner".
_INDEXES = (
    ("ix_mcp_servers_owner_id", "ix_mcp_servers_user_id"),
    ("ix_discovered_tools_owner_id", "ix_discovered_tools_user_id"),
    ("ix_mcp_sessions_owner_id", "ix_mcp_sessions_user_id"),
    ("ix_mcp_sessions_owner_fingerprint_activity", "ix_mcp_sessions_user_fingerprint_activity"),
)
_UNIQUE = ("mcp_servers", "uq_mcp_servers_owner_name", "uq_mcp_servers_user_name")
# Foreign keys are found by column, not name: a database built by `create_all` has Postgres' default
# names (`mcp_servers_owner_id_fkey`), one built by Alembic has `fk_mcp_servers_owner_id`.
_FOREIGN_KEYS = (
    ("mcp_servers", "fk_mcp_servers_owner_id", "fk_mcp_servers_user_id"),
    ("mcp_sessions", "fk_mcp_sessions_owner_id", "fk_mcp_sessions_user_id"),
)


def _rename_fk(table: str, column: str, new_name: str) -> None:
    """Rename the foreign key on `table.column` to `new_name`, whatever it is called now."""
    current = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT c.conname FROM pg_constraint c "
                "JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey) "
                "WHERE c.contype = 'f' AND c.conrelid = CAST(:table AS regclass) AND a.attname = :column"
            ),
            {"table": table, "column": column},
        )
        .scalar()
    )
    if current and current != new_name:
        op.execute(f'ALTER TABLE {table} RENAME CONSTRAINT "{current}" TO {new_name}')


def _rename_unique(table: str, old: str, new: str) -> None:
    op.execute(
        f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = '{old}') "
        f"THEN ALTER TABLE {table} RENAME CONSTRAINT {old} TO {new}; END IF; END $$"
    )


def upgrade() -> None:
    """Every Server, Tool and Session must belong to an account; the column is now `user_id`.

    Rows with no owner (created before accounts existed and never claimed) are deleted, with their
    Executions (via the ON DELETE CASCADE on server_id / session_id).
    """
    op.execute("DELETE FROM mcp_sessions WHERE owner_id IS NULL")
    op.execute("DELETE FROM mcp_servers WHERE owner_id IS NULL")
    op.execute("DELETE FROM discovered_tools WHERE owner_id IS NULL")

    for table in _TABLES:
        op.alter_column(table, "owner_id", new_column_name="user_id", existing_type=sa.String(length=36), nullable=False)
    for old, new in _INDEXES:
        op.execute(f"ALTER INDEX IF EXISTS {old} RENAME TO {new}")
    _rename_unique(*_UNIQUE)
    for table, _old, new in _FOREIGN_KEYS:
        _rename_fk(table, "user_id", new)

    # Tools had no foreign key to their owner; a deleted account now takes its tools with it.
    op.execute("DELETE FROM discovered_tools WHERE user_id NOT IN (SELECT id FROM users)")
    op.create_foreign_key("fk_discovered_tools_user_id", "discovered_tools", "users", ["user_id"], ["id"], ondelete="CASCADE")


def downgrade() -> None:
    """Back to a nullable `owner_id`. Rows deleted by the upgrade cannot be restored."""
    op.drop_constraint("fk_discovered_tools_user_id", "discovered_tools", type_="foreignkey")
    for table, old, _new in _FOREIGN_KEYS:
        _rename_fk(table, "user_id", old)
    table, old, new = _UNIQUE
    _rename_unique(table, new, old)
    for old, new in _INDEXES:
        op.execute(f"ALTER INDEX IF EXISTS {new} RENAME TO {old}")
    for table in _TABLES:
        op.alter_column(table, "user_id", new_column_name="owner_id", existing_type=sa.String(length=36), nullable=True)
