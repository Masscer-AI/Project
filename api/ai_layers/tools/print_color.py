"""
Example tool: print colored text in the terminal.

Useful for testing the AgentLoop — the AI picks a color and prints a message.

Usage:
    from api.ai_layers.agent_loop import AgentLoop
    from api.ai_layers.tools.print_color import get_tool

    loop = AgentLoop(
        tools=[get_tool()],
        instructions="You can print colored messages in the terminal. Use the tool.",
    )
    result = loop.run("Print 'Hello world' in green and then 'Goodbye' in red")
"""

from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Parameters schema (Pydantic — auto-converted to JSON Schema by AgentLoop)
# ---------------------------------------------------------------------------

ColorLiteral = Literal["red", "green", "yellow", "blue", "magenta", "cyan", "white"]

ANSI_COLORS: dict[str, str] = {
    "red": "\033[91m",
    "green": "\033[92m",
    "yellow": "\033[93m",
    "blue": "\033[94m",
    "magenta": "\033[95m",
    "cyan": "\033[96m",
    "white": "\033[97m",
}
ANSI_RESET = "\033[0m"


class PrintColorParams(BaseModel):
    """Parameters for the print_color tool."""

    color: ColorLiteral = Field(
        description="The color to use. One of: red, green, yellow, blue, magenta, cyan, white."
    )
    text: str = Field(
        description="The text to print in the terminal."
    )


# ---------------------------------------------------------------------------
# Tool result schema
# ---------------------------------------------------------------------------

class PrintColorResult(BaseModel):
    """Result returned after printing."""

    success: bool
    message: str


# ---------------------------------------------------------------------------
# Tool function
# ---------------------------------------------------------------------------

def print_color(color: ColorLiteral, text: str) -> PrintColorResult:
    """Print text in the specified color to the terminal."""
    ansi = ANSI_COLORS.get(color, ANSI_COLORS["white"])
    print(f"{ansi}{text}{ANSI_RESET}")
    return PrintColorResult(
        success=True,
        message=f"Printed '{text}' in {color}",
    )


# ---------------------------------------------------------------------------
# Tool config (ready for AgentLoop)
# ---------------------------------------------------------------------------

def get_tool() -> dict:
    """
    Return an AgentTool dict ready to pass to AgentLoop(tools=[...]).

    Example:
        loop = AgentLoop(tools=[get_tool()], instructions="...")
    """
    return {
        "name": "print_color",
        "description": (
            "Print a message in a specific color in the server terminal. "
            "Available colors: red, green, yellow, blue, magenta, cyan, white."
        ),
        "parameters": PrintColorParams,
        "function": print_color,
    }
