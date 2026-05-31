"""
agent.py — a multi-step planning agent in ~140 lines.

The full agent: an LLM client, a tool registry, a planner that returns JSON,
an executor that runs one step, and a loop that walks the whole plan.

Usage from the command line:
    python agent.py "What is 17 * 23 plus today's day-of-month?"
    python agent.py --tools payments "<MT103 message>"

Or import and call run_agent(goal) from your own code.

Requires:  Python 3.10+, the `requests` package, and a running Ollama server
           with the model you pass via --model (default: gemma4:e2b).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Callable, Dict, List


# ─────────────────────────────────────────────────────────────────────────
# 1. LLM CLIENT
# ─────────────────────────────────────────────────────────────────────────

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/chat")
MODEL      = os.environ.get("AGENT_MODEL", "gemma4:e2b")


def llm(system: str, user: str, *, model: str = None, temperature: float = 0.2) -> str:
    """Single chat completion against a local Ollama server.

    The whole agent talks to the model through this one function. Swap it for
    any other backend (Anthropic, OpenAI, vLLM, etc.) and nothing else changes.
    """
    import requests  # local import keeps the top-level imports light

    r = requests.post(
        OLLAMA_URL,
        json={
            "model":    model or MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            "stream":  False,
            "options": {"temperature": temperature},
        },
        timeout=180,
    )
    r.raise_for_status()
    return r.json()["message"]["content"]


# ─────────────────────────────────────────────────────────────────────────
# 2. TOOLS  —  the registry is filled in by whichever toolset is loaded
# ─────────────────────────────────────────────────────────────────────────

TOOLS:     Dict[str, Callable[[str], str]] = {}
TOOL_DOCS: str = ""


def use_toolset(name: str) -> None:
    """Swap in a toolset by name. The agent loop never changes — only TOOLS does."""
    global TOOLS, TOOL_DOCS

    if name == "basics":
        from tools.basics import TOOLS as t, TOOL_DOCS as d
    elif name == "payments":
        from tools.payments import TOOLS as t, TOOL_DOCS as d
    else:
        raise ValueError(f"Unknown toolset: {name!r}. Try 'basics' or 'payments'.")

    TOOLS, TOOL_DOCS = t, d


# ─────────────────────────────────────────────────────────────────────────
# 3. PLANNER  —  one LLM call returns JSON
# ─────────────────────────────────────────────────────────────────────────

PLANNER_PROMPT = """You are the planning module of an AI agent.

Given a user goal, decompose it into 2-6 small ordered steps.
For each step pick ONE tool from this list:
{tools}

You can reference an earlier step's result in the input field
using the placeholder {{step_N}} where N is the step id.

Respond with ONLY valid JSON, no commentary, in this exact shape:
{{
  "steps": [
    {{"id": 1, "description": "...", "tool": "<tool name>", "input": "..."}},
    {{"id": 2, "description": "...", "tool": "<tool name>", "input": "..."}}
  ]
}}
"""


def make_plan(goal: str) -> List[Dict]:
    """Ask the LLM to decompose the goal into a JSON plan. Parse forgivingly."""
    system = PLANNER_PROMPT.format(tools=TOOL_DOCS)
    raw    = llm(system, f"Goal: {goal}")

    # The model sometimes wraps JSON in ```json fences or adds a preamble.
    # Grab the first { ... } block and parse that.
    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        raise ValueError(f"Planner did not return JSON:\n{raw}")

    return json.loads(match.group())["steps"]


# ─────────────────────────────────────────────────────────────────────────
# 4. EXECUTOR  —  one step, one observation
# ─────────────────────────────────────────────────────────────────────────

def execute_step(step: Dict, memory: List[Dict]) -> str:
    """Run a single step. Substitute placeholders. Dispatch to a tool or the LLM."""
    raw_in = step.get("input", "")

    # 1. Fill placeholders like {step_2} with the observation from step 2.
    for past in memory:
        raw_in = raw_in.replace(f"{{step_{past['id']}}}", past["observation"])

    # 2. Dispatch to a real tool, or fall back to the LLM as a "reasoning" step.
    tool = step.get("tool", "reason")
    if tool in TOOLS:
        return TOOLS[tool](raw_in)

    context = "\n".join(f"Step {m['id']}: {m['observation']}" for m in memory)
    user = (
        f"Previous observations:\n{context}\n\n"
        f"Task: {step.get('description', '')}\nInput: {raw_in}\n\n"
        "Give only the answer. No preamble."
    )
    return llm("You execute one step of a plan. Be concise.", user)


# ─────────────────────────────────────────────────────────────────────────
# 5. AGENT LOOP  —  plan, walk, observe, synthesize
# ─────────────────────────────────────────────────────────────────────────

def summarize(memory: List[Dict]) -> str:
    """Format observations for the synthesis LLM call."""
    return "\n".join(f"step {m['id']}: {m['observation']}" for m in memory)


def run_agent(goal: str, *, verbose: bool = True) -> str:
    """Plan, execute, observe, synthesize. Three function calls and a for-loop."""
    if not TOOLS:
        use_toolset("basics")

    if verbose:
        print(f"\nGOAL: {goal}\n")

    # ---- plan ----
    steps = make_plan(goal)
    if verbose:
        print("PLAN")
        for s in steps:
            print(f"  {s['id']}. [{s['tool']:<16}] {s['description']}")

    # ---- execute ----
    memory: List[Dict] = []
    if verbose:
        print("\nEXECUTION")
    for step in steps:
        obs = execute_step(step, memory)
        if verbose:
            preview = obs if len(obs) < 80 else obs[:77] + "..."
            print(f"  step {step['id']} -> {preview}")
        memory.append({"id": step["id"], "observation": obs})

    # ---- synthesize ----
    final = llm(
        "Synthesize a final answer for the user from the observations. Be concise.",
        f"Goal: {goal}\n\nObservations:\n{summarize(memory)}\n\nFinal answer:",
    )
    if verbose:
        print(f"\nANSWER\n{final}\n")
    return final


# ─────────────────────────────────────────────────────────────────────────
# 6. CLI
# ─────────────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="Run the agent against a goal.")
    p.add_argument("goal", nargs="*", help="The goal in plain English.")
    p.add_argument("--tools", default="basics", choices=["basics", "payments"],
                   help="Which tool registry to load (default: basics).")
    p.add_argument("--model", default=None,
                   help="Ollama model tag (overrides AGENT_MODEL env var).")
    args = p.parse_args()

    if args.model:
        global MODEL
        MODEL = args.model

    use_toolset(args.tools)

    goal = " ".join(args.goal) or (
        "What is 17 * 23 plus today's day-of-month, "
        "and how many words are in 'agents plan and act'?"
    )
    run_agent(goal)


if __name__ == "__main__":
    main()
