
from fastmcp import FastMCP

mcp = FastMCP("Remote Calculator Server")


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


@mcp.tool()
def subtract(a: int, b: int) -> int:
    """Subtract the second number from the first."""
    return a - b


@mcp.tool()
def multiply(a: int, b: int) -> int:
    """Multiply two numbers."""
    return a * b


@mcp.tool()
def greet(name: str) -> str:
    """Greet a person."""
    return f"Hello, {name}! Your remote MCP server is working."


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)
