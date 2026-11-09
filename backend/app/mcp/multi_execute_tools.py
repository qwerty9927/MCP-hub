"""Agent-Driven Meta-Tool: MULTI_EXECUTE_TOOLS (Parallel Dispatcher)."""

import asyncio
import inspect
import json
from typing import Annotated, Any
from uuid import UUID

import mcp.types as types
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from pydantic import ValidationError as PydanticValidationError

from app.core.constants.meta_tools import META_TOOL_NAMES, MULTI_EXECUTE_TOOLS_NAME
from app.core.exceptions import AppError, ValidationError
from app.core.logging import logger
from app.helpers.errors import format_mcp_error

MULTI_EXECUTE_TOOLS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "executions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "tool_slug": {
                        "type": "string",
                        "minLength": 1,
                        "description": (
                            "Exact namespaced tool identifier (`tool_slug`) returned by "
                            "SEARCH_TOOLS or listed in the tool catalog (e.g., "
                            "'math-server__add' or 'slack__send_message'). Never invent slugs."
                        ),
                    },
                    "arguments": {
                        "type": "object",
                        "default": {},
                        "description": (
                            "Key-value JSON dictionary of arguments strictly conforming to the "
                            "target tool's `input_schema`. Provide all `required` fields with "
                            "exact data types. Pass an empty object `{}` if the tool takes "
                            "no arguments."
                        ),
                    },
                },
                "required": ["tool_slug", "arguments"],
            },
            "minItems": 1,
            "description": (
                "Non-empty list of independent tool calls to execute concurrently. "
                "Batch independent calls together for speed, but do NOT batch a tool call "
                "that depends on the runtime output of another call in the same request."
            ),
        },
    },
    "required": ["executions"],
}


def get_multi_execute_tool_definition() -> types.Tool:
    """Return MCP Tool definition for MULTI_EXECUTE_TOOLS."""
    return types.Tool(
        name=MULTI_EXECUTE_TOOLS_NAME,
        description=inspect.cleandoc(
            """Concurrently execute one or more downstream tools discovered via `SEARCH_TOOLS`.

            ### Agent Execution Guidelines:
            1. **Strict Schema Compliance:** Every item in `executions` MUST use the exact `tool_slug` and
               provide `arguments` that strictly match the `input_schema` returned by `SEARCH_TOOLS`.
               Never guess or fabricate tool slugs or parameter names.
            2. **Parallel vs. Sequential Chaining:**
               - **Independent Calls:** Group independent tool calls (such as fetching prerequisites from
                 multiple services or running parallel lookups) into a single `MULTI_EXECUTE_TOOLS` call.
               - **Dependent Calls (Data Dependencies):** If Tool B requires an output from Tool A
                 (e.g., `channel_id` returned by `list_channels`), execute Tool A first, inspect its response,
                 and then call `MULTI_EXECUTE_TOOLS` for Tool B in the next turn.
            3. **Partial Failure Handling:** Each tool execution in the batch is isolated and returns its own
               `status` (`"success"`, `"validation_error"`, or `"error"`).
               - If an item returns `"validation_error"`, read the error details, fix the missing/invalid
                 arguments according to the tool's `input_schema`, and retry only the failed tool."""
        ),
        input_schema=MULTI_EXECUTE_TOOLS_SCHEMA,
    )


class ToolExecutionItem(BaseModel):
    """Single tool execution specification for MULTI_EXECUTE_TOOLS."""

    model_config = ConfigDict(extra="forbid")

    tool_slug: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    arguments: dict[str, Any] = Field(default_factory=dict)


class MultiExecuteToolsInput(BaseModel):
    """Pydantic validation schema for MULTI_EXECUTE_TOOLS arguments."""

    model_config = ConfigDict(extra="forbid")

    executions: list[ToolExecutionItem] = Field(..., min_length=1)


async def handle_multi_execute_tools(
    arguments: dict[str, Any],
    tool_map: dict[str, Any],
    tool_router: Any,
    server_registry: Any,
    session_id: str | None = None,
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

            kwargs = {}
            if session_id and isinstance(session_id, str):
                kwargs["session_id"] = session_id

            result = await tool_router.execute_mcp_tool(
                server_id=server_id_val,
                tool_name=mapping.original_tool_name,
                arguments=item.arguments,
                **kwargs,
            )

            if result.is_error:
                error_msg = ""
                if result.content:
                    error_msg = (
                        " ".join(getattr(c, "text", str(c)) for c in result.content if hasattr(c, "text"))
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
                    data_output = [c.model_dump() if hasattr(c, "model_dump") else str(c) for c in result.content]

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
