"""Unit tests for SEARCH_TOOLS pure discovery meta-tool."""

from uuid import uuid4

import pytest

from app.core.constants.meta_tools import (
    MULTI_EXECUTE_TOOLS_NAME,
    SEARCH_TOOLS_NAME,
)
from app.core.exceptions import ValidationError
from app.mcp.search_tools import (
    SEARCH_TOOLS_SCHEMA,
    get_search_tool_definition,
    handle_search_tools,
    score_tool_match,
)
from app.services.mcp_gateway import GatewayToolMapping


def test_search_tool_definition_and_schema():
    tool = get_search_tool_definition()
    assert tool.name == SEARCH_TOOLS_NAME
    assert tool.input_schema == SEARCH_TOOLS_SCHEMA
    assert "queries" in tool.input_schema["required"]
    assert tool.input_schema["additionalProperties"] is False
    assert tool.input_schema["properties"]["queries"]["items"]["minLength"] == 1
    assert tool.input_schema["properties"]["queries"]["items"]["maxLength"] == 256
    assert "### Agent Search & Decomposition Guidelines:" in tool.description
    # Ensure description is cleanly dedented via inspect.cleandoc
    assert not any(line.startswith("            ") for line in tool.description.splitlines())


def test_score_tool_match():
    # 1. Exact match on slug or original name has high score
    s_exact = score_tool_match(
        query="calculate",
        tool_slug="math__calculate",
        original_name="calculate",
        description="Performs math",
        server_name="math_server",
        input_schema={},
    )
    assert s_exact >= 50.0

    # 2. Substring in description
    s_desc = score_tool_match(
        query="addition",
        tool_slug="math__calculate",
        original_name="calculate",
        description="Supports addition and multiplication",
        server_name="math_server",
        input_schema={},
    )
    assert s_desc > 0.0

    # 3. Match in schema properties and property descriptions
    s_schema = score_tool_match(
        query="expression",
        tool_slug="math__calculate",
        original_name="calculate",
        description="A math tool",
        server_name="math_server",
        input_schema={
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Math expression string",
                }
            },
        },
    )
    assert s_schema > 0.0

    # 4. Zero matches
    s_none = score_tool_match(
        query="database query",
        tool_slug="math__calculate",
        original_name="calculate",
        description="A math tool",
        server_name="math_server",
        input_schema={},
    )
    assert s_none == 0.0

    # 5. Empty or whitespace query
    assert score_tool_match("", "math__calc", "calc", "", "", {}) == 0.0
    assert score_tool_match("   ", "math__calc", "calc", "", "", {}) == 0.0


def test_handle_search_tools_ranking_and_deduplication():
    srv1_id = uuid4()
    srv2_id = uuid4()

    tool_map = {
        "math_server__calculate": GatewayToolMapping(
            hub_tool_name="math_server__calculate",
            server_id=srv1_id,
            server_name="math_server",
            original_tool_name="calculate",
            input_schema={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Mathematical expression to evaluate",
                    }
                },
                "required": ["expression"],
            },
            description="Evaluate mathematical expressions",
            availability_status="AVAILABLE",
        ),
        "text_server__transform": GatewayToolMapping(
            hub_tool_name="text_server__transform",
            server_id=srv2_id,
            server_name="text_server",
            original_tool_name="transform",
            input_schema={
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "mode": {"type": "string", "enum": ["upper", "lower"]},
                },
                "required": ["text"],
            },
            description="Transforms text case",
            availability_status="AVAILABLE",
        ),
        "text_server__echo": GatewayToolMapping(
            hub_tool_name="text_server__echo",
            server_id=srv2_id,
            server_name="text_server",
            original_tool_name="echo",
            input_schema={"type": "object", "properties": {"message": {"type": "string"}}},
            description="Echo message",
            availability_status="AVAILABLE",
        ),
    }

    # Query matching calculate via schema parameter 'expression'
    res = handle_search_tools(
        arguments={"queries": ["math expression", "evaluate math"]},
        tool_map=tool_map,
    )
    assert res["matched_count"] == 1
    assert res["tools"][0]["tool_slug"] == "math_server__calculate"
    assert res["tools"][0]["server_id"] == str(srv1_id)
    assert "expression" in res["tools"][0]["input_schema"]["properties"]

    # Multiple queries with top_k=1 per query
    res_multi = handle_search_tools(
        arguments={"queries": ["math calculate", "text uppercase transform"], "top_k": 1},
        tool_map=tool_map,
    )
    assert res_multi["matched_count"] == 2
    slugs = [t["tool_slug"] for t in res_multi["tools"]]
    assert slugs == ["math_server__calculate", "text_server__transform"]

    # Top-k limit
    res_top_k = handle_search_tools(
        arguments={"queries": ["text"], "top_k": 1},
        tool_map=tool_map,
    )
    assert res_top_k["matched_count"] == 1


def test_handle_search_tools_filters_meta_tools():
    tool_map = {
        SEARCH_TOOLS_NAME: GatewayToolMapping(
            hub_tool_name=SEARCH_TOOLS_NAME,
            server_id=uuid4(),
            server_name="hub",
            original_tool_name=SEARCH_TOOLS_NAME,
            input_schema={},
            description="Meta tool",
            availability_status="AVAILABLE",
        ),
        MULTI_EXECUTE_TOOLS_NAME: GatewayToolMapping(
            hub_tool_name=MULTI_EXECUTE_TOOLS_NAME,
            server_id=uuid4(),
            server_name="hub",
            original_tool_name=MULTI_EXECUTE_TOOLS_NAME,
            input_schema={},
            description="Meta tool",
            availability_status="AVAILABLE",
        ),
        "srv__real_tool": GatewayToolMapping(
            hub_tool_name="srv__real_tool",
            server_id=uuid4(),
            server_name="srv",
            original_tool_name="real_tool",
            input_schema={},
            description="Real tool",
            availability_status="AVAILABLE",
        ),
    }

    res = handle_search_tools(
        arguments={"queries": ["meta search execute tool"]},
        tool_map=tool_map,
    )
    slugs = [t["tool_slug"] for t in res["tools"]]
    assert SEARCH_TOOLS_NAME not in slugs
    assert MULTI_EXECUTE_TOOLS_NAME not in slugs
    assert "srv__real_tool" in slugs


def test_handle_search_tools_validation_error():
    # Empty queries list
    with pytest.raises(ValidationError):
        handle_search_tools(arguments={"queries": []}, tool_map={})

    # Missing queries
    with pytest.raises(ValidationError):
        handle_search_tools(arguments={"top_k": 5}, tool_map={})

    # top_k out of bounds
    with pytest.raises(ValidationError):
        handle_search_tools(arguments={"queries": ["test"], "top_k": 50}, tool_map={})

    # Extra unexpected argument (extra="forbid")
    with pytest.raises(ValidationError):
        handle_search_tools(
            arguments={"queries": ["test"], "unexpected_field": True},
            tool_map={},
        )

    # Empty string query item (min_length=1)
    with pytest.raises(ValidationError):
        handle_search_tools(arguments={"queries": [""]}, tool_map={})

    # Whitespace-only query item (stripped to empty)
    with pytest.raises(ValidationError):
        handle_search_tools(arguments={"queries": ["   "]}, tool_map={})

    # Query string exceeding max length 256
    with pytest.raises(ValidationError):
        handle_search_tools(arguments={"queries": ["a" * 257]}, tool_map={})
