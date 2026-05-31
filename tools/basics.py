"""
tools/basics.py — the teaching toolset.

Three tiny tools demonstrate the contract: one string in, one string out.
The agent never knows or cares what these functions do internally.
"""

from __future__ import annotations

from datetime import date


def calculator(expression: str) -> str:
    """Evaluate a math expression like '23 * 47'.

    Uses eval() with no builtins. NOT safe for untrusted input in production —
    swap for a real expression parser (e.g. asteval, simpleeval) before shipping.
    """
    try:
        return str(eval(expression, {"__builtins__": {}}, {}))
    except Exception as e:
        return f"Error: {e}"


def current_date(_: str = "") -> str:
    """Return today's date as YYYY-MM-DD. Input is ignored."""
    return date.today().isoformat()


def word_count(text: str) -> str:
    """Count whitespace-separated tokens in the input string."""
    return str(len(text.split()))


TOOLS = {
    "calculator":   calculator,
    "current_date": current_date,
    "word_count":   word_count,
}

TOOL_DOCS = """
- calculator(expression): Evaluate math. Example input: "23 * 47"
- current_date(): Returns today's date as YYYY-MM-DD. Input is ignored.
- word_count(text): Counts whitespace-separated words. Example: "hello world"
- reason(prompt): No tool — just let the LLM think and answer.
"""
