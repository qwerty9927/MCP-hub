"""Demo MCP Server for testing and local integration.

Provides at least two tools:
- calculate: Evaluates mathematical expressions safely
- echo: Returns manipulated string output
- system_ping: Returns server status and timestamp
"""

import ast
import operator
import sys
from datetime import UTC, datetime
from typing import Any

from mcp.server.mcpserver import MCPServer

# Initialize MCP Server
mcp = MCPServer("demo-mcp-server")

# Safe math operators
SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}


def _safe_eval(node: ast.AST) -> float | int:
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    elif isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    elif isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in SAFE_OPERATORS:
            raise ValueError(f"Unsupported operator: {op_type.__name__}")
        left = _safe_eval(node.left)
        right = _safe_eval(node.right)
        return SAFE_OPERATORS[op_type](left, right)
    elif isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in SAFE_OPERATORS:
            raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
        operand = _safe_eval(node.operand)
        return SAFE_OPERATORS[op_type](operand)
    raise ValueError(f"Unsupported expression node: {type(node).__name__}")


@mcp.tool()
def calculate(expression: str) -> str:
    """Safely calculate a mathematical expression (e.g., '12 + 4 * 2')."""
    try:
        parsed = ast.parse(expression.strip(), mode="eval")
        result = _safe_eval(parsed)
        return str(result)
    except Exception as exc:
        raise ValueError(f"Invalid expression '{expression}': {exc}") from exc


@mcp.tool()
def echo(message: str, uppercase: bool = False, reverse: bool = False) -> str:
    """Echo the input message with optional casing and reversing."""
    output = message
    if uppercase:
        output = output.upper()
    if reverse:
        output = output[::-1]
    return output


@mcp.tool()
def system_ping() -> dict[str, Any]:
    """Return health ping status and ISO timestamp."""
    return {
        "status": "ok",
        "server": "demo-mcp-server",
        "timestamp": datetime.now(UTC).isoformat(),
        "python_version": sys.version,
    }


if __name__ == "__main__":
    # Run in stdio mode by default
    mcp.run("stdio")
