"""Agent-Driven Meta-Tool: SEARCH_TOOLS (Pure Discovery)."""

import inspect
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from mcp.types import Tool
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from pydantic import ValidationError as PydanticValidationError

from app.core.constants.meta_tools import META_TOOL_NAMES, SEARCH_TOOLS_NAME
from app.core.exceptions import ValidationError
from app.domain.tool_entity import ToolEntity
from app.helpers.text import slugify

SEARCH_TOOLS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "queries": {
            "type": "array",
            "items": {
                "type": "string",
                "minLength": 1,
                "maxLength": 256,
            },
            "minItems": 1,
            "description": (
                "List of atomic English search queries describing each single action, resource, "
                "or prerequisite lookup needed to fulfill the task. Split multi-step workflows "
                "into separate queries (1 query per intended tool call). Include the service or "
                "domain name if known, and omit user-specific identifiers or long text. "
                "Examples: ['search github issues', 'list slack channels', 'send slack message']."
            ),
        },
        "top_k": {
            "type": "integer",
            "minimum": 1,
            "maximum": 20,
            "default": 5,
            "description": (
                "Maximum number of candidate tools to return per query (default: 5). "
                "Increase to 10-15 if the initial search does not return the expected tool "
                "or if exploring a broad domain."
            ),
        },
    },
    "required": ["queries"],
}


# (queries, top_k) -> for each query, (Tool, cosine similarity) pairs, best first
ToolSearch = Callable[[list[str], int], Awaitable[list[list[tuple[ToolEntity, float]]]]]


class SearchToolsInput(BaseModel):
    """Pydantic validation schema for SEARCH_TOOLS arguments."""

    model_config = ConfigDict(extra="forbid")

    queries: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=256)]] = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


def get_search_tool_definition() -> Tool:
    """Return MCP Tool definition for SEARCH_TOOLS."""
    return Tool(
        name=SEARCH_TOOLS_NAME,
        description=inspect.cleandoc(
            """Discover available downstream tools across all connected MCP servers by action, keyword, or domain.
            Always call this tool FIRST before attempting to execute unfamiliar tools or when you need to verify
            a tool's exact `tool_slug` and JSON `input_schema`.

            ### Agent Search & Decomposition Guidelines:
            1. **Atomic Queries (1 Query = 1 Action):** Split complex, multi-step user requests into separate,
               atomic search strings inside `queries` (e.g., `["list slack channels", "send slack message"]`).
            2. **Search for Hidden Prerequisites:** If an action requires an opaque ID you do not have yet
               (e.g., you have a channel name, repo name, or username, but the target API likely needs an ID),
               proactively include a lookup/search query in the same batch (e.g., `"find user by name"`).
            3. **Normalize Queries (No PII/Specific Values):** Keep queries focused on the functional action and
               app/domain name. Do NOT include specific emails, UUIDs, or long message bodies in search queries.
            4. **English Keywords:** Always write search queries in English using standard API verbs
               (`list`, `get`, `search`, `create`, `update`, `delete`, `send`).

            ### How to Handle the Response:
            - Review the returned `tools` list, paying close attention to each tool's `tool_slug` and
               `input_schema` (especially `required` fields and parameter descriptions).
            - You are responsible for deciding which discovered tools to call and in what order.
            - Pass the selected `tool_slug` and schema-compliant `arguments` to `MULTI_EXECUTE_TOOLS`."""
        ),
        input_schema=SEARCH_TOOLS_SCHEMA,
    )


async def handle_search_tools(arguments: dict[str, Any], search: ToolSearch) -> dict[str, Any]:
    """Execute SEARCH_TOOLS: rank the caller's Tools by vector similarity to each query (ADR-0006)."""
    try:
        validated = SearchToolsInput.model_validate(arguments)
    except PydanticValidationError as err:
        raise ValidationError(
            f"Invalid arguments for {SEARCH_TOOLS_NAME}: {err}",
            details={"errors": err.errors()},
        ) from err

    results = await search(validated.queries, validated.top_k)

    seen_slugs: set[str] = set()
    matched_tools: list[dict[str, Any]] = []
    for ranked in results:
        for tool, similarity in ranked:
            if tool.name in META_TOOL_NAMES:
                continue
            slug = f"{slugify(tool.server_name)}__{tool.name}" if tool.server_name else tool.name
            if slug in seen_slugs:
                continue
            seen_slugs.add(slug)
            matched_tools.append(
                {
                    "tool_slug": slug,
                    "server_id": str(tool.server_id),
                    "description": tool.description,
                    "input_schema": tool.input_schema,
                    "similarity": round(similarity, 3),
                }
            )

    return {
        "matched_count": len(matched_tools),
        "tools": matched_tools,
    }
