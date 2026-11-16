"""Unit tests for SEARCH_TOOLS: argument validation and shaping the ranked results (ranking itself is pgvector's)."""

from uuid import uuid4

import pytest

from app.core.constants.meta_tools import (
    MULTI_EXECUTE_TOOLS_NAME,
    SEARCH_TOOLS_NAME,
)
from app.core.exceptions import ValidationError
from app.domain.tool_entity import ToolEntity
from app.mcp.search_tools import (
    SEARCH_TOOLS_SCHEMA,
    get_search_tool_definition,
    handle_search_tools,
)

USER_ID = uuid4()  # owner for entities in these mock-only tests


def tool(name: str, server_name: str = "math server", description: str | None = None) -> ToolEntity:
    return ToolEntity(
        id=uuid4(),
        server_id=uuid4(),
        server_name=server_name,
        name=name,
        input_schema={"type": "object"},
        description=description,
        user_id=USER_ID,
    )


def search_returning(*ranked: list[tuple[ToolEntity, float]]):
    """A search function that returns `ranked` (one list per query) and records what it was asked."""
    calls: list[tuple[list[str], int]] = []

    async def search(queries: list[str], top_k: int) -> list[list[tuple[ToolEntity, float]]]:
        calls.append((queries, top_k))
        return list(ranked)

    search.calls = calls  # type: ignore[attr-defined]
    return search


def test_search_tool_definition_and_schema():
    definition = get_search_tool_definition()
    assert definition.name == SEARCH_TOOLS_NAME
    assert definition.input_schema == SEARCH_TOOLS_SCHEMA
    assert "queries" in definition.input_schema["required"]
    assert definition.input_schema["additionalProperties"] is False
    assert definition.input_schema["properties"]["queries"]["items"]["minLength"] == 1
    assert definition.input_schema["properties"]["queries"]["items"]["maxLength"] == 256
    assert "### Agent Search & Decomposition Guidelines:" in definition.description
    # Ensure description is cleanly dedented via inspect.cleandoc
    assert not any(line.startswith("            ") for line in definition.description.splitlines())


async def test_results_keep_rank_order_shape_and_similarity():
    calc, add = tool("calculate", description="Evaluate math"), tool("add")
    search = search_returning([(calc, 0.91234), (add, 0.5)])

    res = await handle_search_tools({"queries": ["calculate expression"], "top_k": 3}, search)

    assert search.calls == [(["calculate expression"], 3)]
    assert res["matched_count"] == 2
    assert res["tools"][0] == {
        "tool_slug": "math_server__calculate",
        "server_id": str(calc.server_id),
        "description": "Evaluate math",
        "input_schema": {"type": "object"},
        "similarity": 0.912,
    }
    assert [t["tool_slug"] for t in res["tools"]] == ["math_server__calculate", "math_server__add"]


async def test_a_tool_found_by_several_queries_is_listed_once():
    calc, echo = tool("calculate"), tool("echo", server_name="echo")
    search = search_returning([(calc, 0.9)], [(calc, 0.8), (echo, 0.7)])

    res = await handle_search_tools({"queries": ["calculate", "echo text"]}, search)

    assert [t["tool_slug"] for t in res["tools"]] == ["math_server__calculate", "echo__echo"]
    assert search.calls == [(["calculate", "echo text"], 5)]  # default top_k


async def test_meta_tools_are_never_returned():
    real = tool("real_tool", server_name="srv")
    search = search_returning([(tool(SEARCH_TOOLS_NAME, "hub"), 0.99), (tool(MULTI_EXECUTE_TOOLS_NAME, "hub"), 0.98), (real, 0.5)])

    res = await handle_search_tools({"queries": ["meta search execute tool"]}, search)

    assert [t["tool_slug"] for t in res["tools"]] == ["srv__real_tool"]


async def test_no_matches_is_an_empty_list():
    res = await handle_search_tools({"queries": ["anything"]}, search_returning([]))
    assert res == {"matched_count": 0, "tools": []}


@pytest.mark.parametrize(
    "arguments",
    [
        {"queries": []},  # empty list
        {"top_k": 5},  # missing queries
        {"queries": ["test"], "top_k": 50},  # top_k out of bounds
        {"queries": ["test"], "unexpected_field": True},  # extra="forbid"
        {"queries": [""]},  # empty item
        {"queries": ["   "]},  # whitespace-only item
        {"queries": ["a" * 257]},  # longer than 256
    ],
)
async def test_invalid_arguments_raise_before_searching(arguments):
    search = search_returning()
    with pytest.raises(ValidationError):
        await handle_search_tools(arguments, search)
    assert search.calls == []
