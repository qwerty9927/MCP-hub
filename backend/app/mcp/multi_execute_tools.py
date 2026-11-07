"""Agent-Driven Meta-Tool: MULTI_EXECUTE_TOOLS (Parallel Dispatcher)."""

import asyncio
import json
from typing import Any
from uuid import UUID

import mcp.types as types
from pydantic import BaseModel, Field
from pydantic import ValidationError as PydanticValidationError

from app.constants.meta_tools import META_TOOL_NAMES, MULTI_EXECUTE_TOOLS_NAME
from app.core.exceptions import AppError, ValidationError
from app.core.logging import logger
from app.helpers.errors import format_mcp_error

MULTI_EXECUTE_TOOLS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "executions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "tool_slug": {
                        "type": "string",
                        "description": "Exact tool slug discovered from SEARCH_TOOLS or catalog.",
                    },
                    "arguments": {
                        "type": "object",
                        "description": "Arguments matching the downstream tool's input schema.",
                    },
                },
                "required": ["tool_slug", "arguments"],
            },
            "minItems": 1,
            "description": "List of tool execution specifications to dispatch concurrently.",
        },
    },
    "required": ["executions"],
}


def get_multi_execute_tool_definition() -> types.Tool:
    """Return MCP Tool definition for MULTI_EXECUTE_TOOLS."""
    return types.Tool(
        name=MULTI_EXECUTE_TOOLS_NAME,
        description=(
            "Parallel dispatcher meta-tool. Executes multiple downstream tool calls "
            "concurrently, preserving validation, audit logging, and per-tool failure "
            "isolation."
        ),
        input_schema=MULTI_EXECUTE_TOOLS_SCHEMA,
    )


class ToolExecutionItem(BaseModel):
    """Single tool execution specification for MULTI_EXECUTE_TOOLS."""

    tool_slug: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class MultiExecuteToolsInput(BaseModel):
    """Pydantic validation schema for MULTI_EXECUTE_TOOLS arguments."""

    executions: list[ToolExecutionItem] = Field(..., min_length=1)


async def handle_multi_execute_tools(
    arguments: dict[str, Any],
    tool_map: dict[str, Any],
    tool_router: Any,
    server_registry: Any,
) -> dict[str, Any]:
    """Execute MULTI_EXECUTE_TOOLS parallel dispatcher with isolated failure handling."""
    try:
        validated = MultiExecuteToolsInput.model_validate(arguments)
    except PydanticValidationError as err:
        raise ValidationError(
            f"Invalid arguments for {MULTI_EXECUTE_TOOLS_NAME}: {err}",
            details={"errors": err.errors()},
        ) from err

    async def _execute_single(item: ToolExecutionItem) -> dict[str, Any]:
        slug = item.tool_slug

        # Disallow recursive meta-tool execution
        if slug in META_TOOL_NAMES:
            return {
                "tool_slug": slug,
                "status": "error",
                "data": None,
                "error": f"Executing meta-tool '{slug}' via {MULTI_EXECUTE_TOOLS_NAME} is not permitted.",
            }

        mapping = tool_map.get(slug)
        if not mapping:
            return {
                "tool_slug": slug,
                "status": "error",
                "data": None,
                "error": f"Unknown or unavailable tool: '{slug}'",
            }

        try:
            # Check server availability
            server_id_val = mapping.server_id
            if isinstance(server_id_val, str):
                server_id_val = UUID(server_id_val)

            server = await server_registry.get_server_entity(server_id_val)
            if not server.enabled:
                return {
                    "tool_slug": slug,
                    "status": "error",
                    "data": None,
                    "error": f"Target server '{mapping.server_name}' is currently disabled",
                }

            result = await tool_router.execute_mcp_tool(
                server_id=server_id_val,
                tool_name=mapping.original_tool_name,
                arguments=item.arguments,
            )

            if result.is_error:
                error_msg = ""
                if result.content:
                    error_msg = (
                        " ".join(
                            getattr(c, "text", str(c)) for c in result.content if hasattr(c, "text")
                        )
                        or "Downstream tool reported an error"
                    )
                return {
                    "tool_slug": slug,
                    "status": "error",
                    "data": None,
                    "error": error_msg,
                }

            # Unpack content for result data
            data_output: Any = None
            if result.content:
                if len(result.content) == 1 and hasattr(result.content[0], "text"):
                    text_val = result.content[0].text
                    try:
                        parsed = json.loads(text_val)
                        data_output = parsed if isinstance(parsed, (dict, list)) else text_val
                    except Exception:
                        data_output = text_val
                else:
                    data_output = [
                        c.model_dump() if hasattr(c, "model_dump") else str(c)
                        for c in result.content
                    ]

            return {
                "tool_slug": slug,
                "status": "success",
                "data": data_output,
                "error": None,
            }

        except ValidationError as val_err:
            logger.warning(f"Validation error in multi-execute item '{slug}': {val_err.message}")
            return {
                "tool_slug": slug,
                "status": "validation_error",
                "data": None,
                "error": f"Argument validation failed: {val_err.message}",
            }
        except AppError as app_err:
            logger.error(f"AppError in multi-execute item '{slug}': {app_err}")
            return {
                "tool_slug": slug,
                "status": "error",
                "data": None,
                "error": format_mcp_error(app_err),
            }
        except Exception as exc:
            logger.error(f"Unexpected error in multi-execute item '{slug}': {exc}")
            return {
                "tool_slug": slug,
                "status": "error",
                "data": None,
                "error": format_mcp_error(exc),
            }

    tasks = [_execute_single(item) for item in validated.executions]
    results = await asyncio.gather(*tasks)

    return {"results": list(results)}
