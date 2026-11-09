"""Validation helpers for schemas, tool arguments, and inputs."""

from typing import Any

import jsonschema
from jsonschema.exceptions import ValidationError as JSONSchemaValidationError

from app.core.exceptions import ValidationError


def validate_tool_arguments(
    arguments: dict[str, Any],
    input_schema: dict[str, Any] | None,
    tool_name: str,
) -> None:
    """Validate tool execution arguments against the tool's input JSON schema."""
    if input_schema and isinstance(input_schema, dict) and (input_schema.get("type") == "object" or "properties" in input_schema):
        try:
            jsonschema.validate(instance=arguments, schema=input_schema)
        except JSONSchemaValidationError as val_err:
            raise ValidationError(
                f"Invalid arguments for tool '{tool_name}': {val_err.message}",
                details={"path": list(val_err.path), "schema_error": val_err.message},
            ) from val_err
