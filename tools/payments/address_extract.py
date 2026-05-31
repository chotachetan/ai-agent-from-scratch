"""
address_extract.py — the one tool that actually calls the LLM.

Free-text SWIFT addresses (35 chars × 4 lines, no schema) become structured
ISO 20022 fields:
  - building_number
  - street_name
  - town_name
  - postal_code
  - country (ISO 3166-1 alpha-2)
  - confidence (0.0-1.0)

This is exactly the part of MT->ISO 20022 conversion that deterministic
converters fail on. It's why the agent earns its keep: scope the LLM to the
one fuzzy task, keep everything else mechanical.
"""

from __future__ import annotations

import json
import re

# Import lazily inside the function so this module loads cleanly even when
# the LLM backend is unreachable (useful for unit tests).


SYSTEM_PROMPT = """You are a payments-data extraction assistant.

You convert a free-text postal address (1-4 lines as it appears in a SWIFT MT
message) into structured ISO 20022 fields.

Output ONLY a valid JSON object with these keys:
  - "building_number": string or empty
  - "street_name":     string
  - "town_name":       string
  - "postal_code":     string or empty
  - "country":         ISO 3166-1 alpha-2 country code (e.g. "US", "GB", "DE")
  - "confidence":      number between 0.0 and 1.0

Rules:
  - Do NOT include any commentary, markdown fences, or explanation.
  - If a field is missing or unclear, return an empty string for it and lower
    the confidence accordingly.
  - "confidence" reflects how certain you are the structured fields are correct
    for the original free text. 1.0 = certain, 0.0 = guessing.
"""


def _safe_parse_json(raw: str) -> dict:
    """Grab the first {...} block and parse it. Tolerates fences and preamble."""
    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        return {
            "building_number": "", "street_name": "", "town_name": "",
            "postal_code":     "", "country":     "", "confidence":  0.0,
        }
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return {
            "building_number": "", "street_name": "", "town_name": "",
            "postal_code":     "", "country":     "", "confidence":  0.0,
        }


def address_extract(address_block: str) -> str:
    """Convert a free-text address block to structured ISO 20022 fields (JSON).

    Calls the LLM. Returns a JSON string per the agent tool contract.
    """
    if not address_block or not address_block.strip():
        return json.dumps({
            "building_number": "", "street_name": "", "town_name": "",
            "postal_code":     "", "country":     "", "confidence":  0.0,
        })

    # Import here to avoid a hard dependency on the running LLM at module load.
    from agent import llm

    user = f"Free-text address:\n{address_block.strip()}\n\nStructured JSON:"
    raw  = llm(SYSTEM_PROMPT, user, temperature=0.1)

    parsed = _safe_parse_json(raw)

    # Normalize: every key present, types stable.
    out = {
        "building_number": str(parsed.get("building_number", "") or ""),
        "street_name":     str(parsed.get("street_name",     "") or ""),
        "town_name":       str(parsed.get("town_name",       "") or ""),
        "postal_code":     str(parsed.get("postal_code",     "") or ""),
        "country":         str(parsed.get("country",         "") or "").upper()[:2],
        "confidence":      float(parsed.get("confidence", 0.0) or 0.0),
    }
    return json.dumps(out, indent=2)
