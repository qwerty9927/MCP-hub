"""Text formatting and string manipulation helpers."""

import re


def slugify(name: str, default: str = "server") -> str:
    """Convert an arbitrary name string to a safe alphanumeric snake_case slug.

    Examples:
        slugify("Github Tools") -> "github_tools"
        slugify("Postgres-DB #1") -> "postgres_db_1"
        slugify("  --- special ---  ") -> "special"
        slugify("!!!") -> "server"
    """
    cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", name.strip()).strip("_").lower()
    return cleaned if cleaned else default
