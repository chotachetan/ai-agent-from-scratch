"""
examples/01_hello_agent.py — your first run.

Runs the agent with the teaching toolset against a simple multi-step goal.
This is the example from the carousel: a calculator + date + word count
combined into one question.

Prerequisites:
    1. Install Ollama and run `ollama serve` in another terminal.
    2. Pull a small model:  ollama pull gemma4:e2b
    3. From the repo root:   python examples/01_hello_agent.py
"""

from __future__ import annotations

import os
import sys

# Make the repo root importable when running from anywhere
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agent import use_toolset, run_agent


def main() -> None:
    use_toolset("basics")

    goal = (
        "What is 17 * 23 plus today's day-of-month, "
        "and how many words are in 'agents plan and act'?"
    )
    run_agent(goal)


if __name__ == "__main__":
    main()
