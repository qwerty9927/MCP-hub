"""Agent-Driven Meta-Tool: MULTI_EXECUTE_TOOLS (Parallel Dispatcher)."""

import asyncio
import inspect
import json
from typing import Annotated, Any

from mcp.types import Tool
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from pydantic import ValidationError as PydanticValidationError

from app.core.constants.meta_tools import META_TOOL_NAMES, MULTI_EXECUTE_TOOLS_NAME
from app.core.enums.execution_enum import ExecutionOutcomeKind, RejectionReason
from app.core.exceptions import ValidationError
from app.core.logging import logger
from app.helpers.errors import format_mcp_error
from app.services.tool_executor import ExecutionOutcome, ToolExecutor

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


def get_multi_execute_tool_definition() -> Tool:
    """Return MCP Tool definition for MULTI_EXECUTE_TOOLS."""
    return Tool(
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


def _agent_data(content: list[dict[str, Any]]) -> Any:
    """Shape content blocks for agents: a single text block is JSON-decoded when possible."""
    if not content:
        return None
    if len(content) == 1 and content[0].get("type") == "text" and "text" in content[0]:
        text_val = content[0]["text"]
        try:
            parsed = json.loads(text_val)
        except (TypeError, ValueError):
            return text_val
        return parsed if isinstance(parsed, (dict, list)) else text_val
    return content


def _agent_result(outcome: ExecutionOutcome) -> dict[str, Any]:
    """Map an Execution Outcome onto the agent-facing per-item result."""
    slug = outcome.tool_reference
    if outcome.kind == ExecutionOutcomeKind.SUCCEEDED:
        return {"tool_slug": slug, "status": "success", "data": _agent_data(outcome.content), "error": None}
    if outcome.rejection_reason == RejectionReason.INVALID_ARGUMENTS:
        return {
            "tool_slug": slug,
            "status": "validation_error",
            "data": None,
            "error": f"Argument validation failed: {outcome.error_message}",
        }
    return {"tool_slug": slug, "status": "error", "data": None, "error": outcome.error_message}


async def execute_single_tool(
    item: ToolExecutionItem,
    executor: ToolExecutor,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Execute one batch item through the Execution module, isolating any failure to this item."""
    slug = item.tool_slug

    if slug in META_TOOL_NAMES or slug in ("Search", "Multi-Execute"):
        return {
            "tool_slug": slug,
            "status": "error",
            "data": None,
            "error": f"Executing meta-tool '{slug}' via {MULTI_EXECUTE_TOOLS_NAME} is not permitted.",
        }

    try:
        outcome = await executor.execute(slug, item.arguments, session_id=session_id)
    except Exception as exc:
        logger.error(f"Unexpected error in multi-execute item '{slug}': {exc}")
        return {"tool_slug": slug, "status": "error", "data": None, "error": format_mcp_error(exc)}
    return _agent_result(outcome)


async def handle_multi_execute_tools(
    arguments: dict[str, Any],
    executor: ToolExecutor,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Execute MULTI_EXECUTE_TOOLS: validate the batch, fan out concurrently, isolate failures per item."""
    try:
        validated = MultiExecuteToolsInput.model_validate(arguments)
    except PydanticValidationError as err:
        raise ValidationError(
            f"Invalid arguments for {MULTI_EXECUTE_TOOLS_NAME}: {err}",
            details={"errors": err.errors()},
        ) from err

    results = await asyncio.gather(*(execute_single_tool(item, executor, session_id) for item in validated.executions))
    return {"results": list(results)}
