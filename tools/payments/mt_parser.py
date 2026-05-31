"""
mt_parser.py — deterministic SWIFT MT103 tokenizer.

Parses the fields the agent cares about for ISO 20022 conversion:
  :20:   Sender's reference
  :32A:  Value date, currency, amount
  :50K:  Ordering customer (account + name + address)
  :59:   Beneficiary (account + name + address)
  :70:   Remittance information

This is pure string parsing — no LLM. The point of the agent isn't to do
work the deterministic code can already do; it's to handle the parts that
genuinely need reasoning (see address_extract.py).
"""

from __future__ import annotations

import json
import re
from typing import Dict, List


def _block_lines(block: str) -> Dict[str, str]:
    """Split a :50K:/:59: block into account + name + address_block."""
    lines = [ln for ln in block.split("\n") if ln.strip()]
    if not lines:
        return {"account": "", "name": "", "address_block": ""}

    # First line is /ACCOUNTNUMBER if it starts with a slash.
    account, name_address = "", lines
    if lines[0].startswith("/"):
        account = lines[0][1:].strip()
        name_address = lines[1:]

    name = name_address[0].strip() if name_address else ""
    address_block = "\n".join(ln.strip() for ln in name_address[1:])
    return {"account": account, "name": name, "address_block": address_block}


def mt_parser(mt_message: str) -> str:
    """Parse an MT103 message into a JSON string. Returns text in/out as per the
    agent tool contract."""
    text = mt_message.strip()

    # Split on field markers like ":20:", ":32A:", ":50K:", ":59:", ":70:".
    # Each field's value is everything up to the next marker.
    field_pattern = re.compile(r":([0-9]{2}[A-Z]?):", re.MULTILINE)
    parts = field_pattern.split(text)

    fields: Dict[str, str] = {}
    # parts[0] is preamble; then alternating tag, value, tag, value, ...
    for i in range(1, len(parts) - 1, 2):
        tag, value = parts[i], parts[i + 1].strip()
        fields[tag] = value

    out: Dict[str, object] = {}

    # 32A = YYMMDD CCY AMOUNT  (e.g. 260526USD1500,00)
    if "32A" in fields:
        m = re.match(r"([0-9]{6})([A-Z]{3})([0-9,\.]+)", fields["32A"])
        if m:
            yymmdd, ccy, amt = m.groups()
            out["value_date"] = f"20{yymmdd[0:2]}-{yymmdd[2:4]}-{yymmdd[4:6]}"
            out["currency"]   = ccy
            out["amount"]     = amt.replace(",", ".")

    if "20" in fields:
        out["sender_reference"] = fields["20"].splitlines()[0].strip()

    if "50K" in fields:
        parts50 = _block_lines(fields["50K"])
        out["sender_account"]        = parts50["account"]
        out["sender_name"]           = parts50["name"]
        out["sender_address_block"]  = parts50["address_block"]

    if "59" in fields:
        parts59 = _block_lines(fields["59"])
        out["beneficiary_account"]       = parts59["account"]
        out["beneficiary_name"]          = parts59["name"]
        out["beneficiary_address_block"] = parts59["address_block"]

    if "70" in fields:
        out["remittance_info"] = fields["70"].replace("\n", " ").strip()

    return json.dumps(out, indent=2)
