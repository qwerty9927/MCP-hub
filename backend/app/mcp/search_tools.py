"""Agent-Driven Meta-Tool: SEARCH_TOOLS (Pure Discovery)."""

import re
from typing import Any

import mcp.types as types
from pydantic import BaseModel, Field
from pydantic import ValidationError as PydanticValidationError

from app.constants.meta_tools import META_TOOL_NAMES, SEARCH_TOOLS_NAME
from app.core.exceptions import ValidationError

SEARCH_TOOLS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "queries": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "description": "List of atomic search queries describing actions or tools needed.",
        },
        "top_k": {
            "type": "integer",
            "minimum": 1,
            "maximum": 20,
            "default": 5,
            "description": "Maximum number of candidate tools to return per query (default 5).",
        },
    },
    "required": ["queries"],
}


def get_search_tool_definition() -> types.Tool:
    """Return MCP Tool definition for SEARCH_TOOLS."""
    return types.Tool(
        name=SEARCH_TOOLS_NAME,
        description=(
            "Pure discovery meta-tool. Searches available tools across downstream servers "
            "using atomic queries and returns candidate tool definitions (slug, server_id, "
            "description, input_schema) scored by relevance."
        ),
        input_schema=SEARCH_TOOLS_SCHEMA,
    )


class SearchToolsInput(BaseModel):
    """Pydantic validation schema for SEARCH_TOOLS arguments."""

    queries: list[str] = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


def _tokenize(text: str) -> list[str]:
    """Extract lowercase alphanumeric tokens from text."""
    return [t.lower() for t in re.split(r"[_\W]+", text) if t]


def score_tool_match(
    query: str,
    tool_slug: str,
    original_name: str,
    description: str | None,
    server_name: str,
    input_schema: dict[str, Any],
) -> float:
    """Calculate relevance score for a tool against a single search query."""
    q_norm = query.strip().lower()
    if not q_norm:
        return 0.0

    q_tokens = _tokenize(q_norm)
    if not q_tokens:
        return 0.0

    score = 0.0
    slug_norm = tool_slug.lower()
    name_norm = original_name.lower()
    desc_norm = (description or "").lower()
    srv_norm = server_name.lower()

    # 1. Exact match on slug or original name
    if q_norm in (slug_norm, name_norm):
        score += 50.0
    # 2. Substring match on slug or original name
    elif q_norm in slug_norm or q_norm in name_norm:
        score += 25.0

    slug_tokens = set(_tokenize(slug_norm))
    name_tokens = set(_tokenize(name_norm))
    desc_tokens = set(_tokenize(desc_norm))
    srv_tokens = set(_tokenize(srv_norm))

    # 3. Token matches in tool name/slug
    for tok in q_tokens:
        if tok in name_tokens or tok in slug_tokens:
            score += 10.0

    # 4. Description matching
    if desc_norm and q_norm in desc_norm:
        score += 15.0
    for tok in q_tokens:
        if tok in desc_tokens:
            score += 5.0

    # 5. Server name matching
    for tok in q_tokens:
        if tok in srv_tokens:
            score += 3.0

    # 6. Schema properties matching (parameter names and descriptions)
    if isinstance(input_schema, dict):
        properties = input_schema.get("properties")
        if isinstance(properties, dict):
            for prop_name, prop_val in properties.items():
                prop_tokens = set(_tokenize(prop_name))
                for tok in q_tokens:
                    if tok in prop_tokens:
                        score += 8.0

                if isinstance(prop_val, dict):
                    prop_desc = str(prop_val.get("description", "")).lower()
                    if prop_desc:
                        if q_norm in prop_desc:
                            score += 10.0
                        prop_desc_tokens = set(_tokenize(prop_desc))
                        for tok in q_tokens:
                            if tok in prop_desc_tokens:
                                score += 4.0

    return score


def handle_search_tools(
    arguments: dict[str, Any] | None = None,
    queries: list[str] | None = None,
    top_k: int = 5,
    tool_map: dict[str, Any] | None = None,
    tools: list[Any] | None = None,
) -> dict[str, Any]:
    """Execute SEARCH_TOOLS pure discovery across available tools."""
    # Validate arguments
    try:
        if arguments is not None:
            validated = SearchToolsInput.model_validate(arguments)
            search_queries = validated.queries
            effective_top_k = validated.top_k
        else:
            validated = SearchToolsInput(queries=queries or [], top_k=top_k)
            search_queries = validated.queries
            effective_top_k = validated.top_k
    except PydanticValidationError as err:
        raise ValidationError(
            f"Invalid arguments for {SEARCH_TOOLS_NAME}: {err}",
            details={"errors": err.errors()},
        ) from err

    # Normalize candidate list from tool_map or tools
    candidates: list[dict[str, Any]] = []

    if tool_map:
        for slug, mapping in tool_map.items():
            if slug in META_TOOL_NAMES:
                continue
            candidates.append(
                {
                    "tool_slug": getattr(mapping, "hub_tool_name", slug),
                    "server_id": str(getattr(mapping, "server_id", "")),
                    "server_name": getattr(mapping, "server_name", ""),
                    "original_name": getattr(mapping, "original_tool_name", slug),
                    "description": getattr(mapping, "description", None),
                    "input_schema": getattr(mapping, "input_schema", {}),
                }
            )
    elif tools:
        for t in tools:
            name = getattr(t, "name", "")
            if name in META_TOOL_NAMES:
                continue
            srv_name = getattr(t, "server_name", "")
            slug = getattr(t, "id", None) or f"{srv_name}__{name}" if srv_name else name
            candidates.append(
                {
                    "tool_slug": getattr(t, "hub_tool_name", slug),
                    "server_id": str(getattr(t, "server_id", "")),
                    "server_name": srv_name,
                    "original_name": name,
                    "description": getattr(t, "description", None),
                    "input_schema": getattr(t, "input_schema", {}),
                }
            )

    seen_slugs: set[str] = set()
    matched_tools: list[dict[str, Any]] = []

    for query in search_queries:
        scored_for_query: list[tuple[float, dict[str, Any]]] = []
        for cand in candidates:
            score = score_tool_match(
                query=query,
                tool_slug=cand["tool_slug"],
                original_name=cand["original_name"],
                description=cand["description"],
                server_name=cand["server_name"],
                input_schema=cand["input_schema"],
            )
            if score > 0.0:
                scored_for_query.append((score, cand))

        # Sort descending by score, tiebreaker on tool_slug
        scored_for_query.sort(key=lambda pair: (-pair[0], pair[1]["tool_slug"]))
        top_candidates = scored_for_query[:effective_top_k]

        for _, cand in top_candidates:
            slug = cand["tool_slug"]
            if slug not in seen_slugs:
                seen_slugs.add(slug)
                matched_tools.append(
                    {
                        "tool_slug": cand["tool_slug"],
                        "server_id": cand["server_id"],
                        "description": cand["description"],
                        "input_schema": cand["input_schema"],
                    }
                )

    return {
        "matched_count": len(matched_tools),
        "tools": matched_tools,
    }
