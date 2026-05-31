"""
examples/02_iso20022_demo.py — the BFSI payoff.

The same agent.py from example 01, with the payments toolset loaded instead.
Reads a real MT103 fixture, asks the agent to convert it to ISO 20022
pacs.008, and prints the validated XML.

This is the carousel's promise: same skeleton, new tools, real banking work.

Prerequisites:
    1. Ollama running with a small model (see examples/01_hello_agent.py).
    2. From the repo root:  python examples/02_iso20022_demo.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Make the repo root importable when running from anywhere
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agent import use_toolset, run_agent


def main() -> None:
    use_toolset("payments")

    sample_path = Path(__file__).parent.parent / "samples" / "mt103_sample.txt"
    mt_message = sample_path.read_text()

    print("=" * 72)
    print("INPUT MT103 MESSAGE")
    print("=" * 72)
    print(mt_message)

    goal = (
        "Convert the following MT103 message to a validated ISO 20022 pacs.008 "
        "XML fragment. Workflow:\n"
        "  1. Use mt_parser to tokenize the MT message into JSON.\n"
        "  2. Use address_extract on each address block "
        "(sender and beneficiary) to produce structured ISO 20022 addresses.\n"
        "  3. Use pacs008_compose to build the XML, passing a JSON object that "
        "merges the parsed MT fields with the two structured addresses under "
        "keys 'sender_address' and 'beneficiary_address'.\n"
        "  4. Use schema_validate to confirm the XML is valid.\n\n"
        f"MT103 message:\n{mt_message}"
    )

    run_agent(goal)


if __name__ == "__main__":
    main()
