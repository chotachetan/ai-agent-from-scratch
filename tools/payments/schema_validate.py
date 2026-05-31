"""
schema_validate.py — validate the generated pacs.008 fragment.

Two layers of validation:

  1. STRUCTURAL — the XML must be well-formed and contain the elements
     a pacs.008 CdtTrfTxInf block requires (PmtId/EndToEndId, IntrBkSttlmAmt,
     Dbtr, Cdtr). This is a lightweight stand-in for a full XSD check.

  2. SEMANTIC INVARIANTS — fields that MUST be present:
       - Amount > 0
       - Currency is a 3-letter code
       - Country is a 2-letter ISO code
       - At least one of (BldgNb, StrtNm) is present per address
       - EndToEndId is non-empty

If you want a full XSD validation, install lxml and load the official
pacs.008.001.08 schema from ISO 20022's catalog. The deterministic check
here is what the carousel's "output audit" tool maps to.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET


PACS_NS = "urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08"
NS_MAP  = {"p": PACS_NS}

REQUIRED_ELEMS = [
    "p:FIToFICstmrCdtTrf",
    "p:FIToFICstmrCdtTrf/p:CdtTrfTxInf",
    "p:FIToFICstmrCdtTrf/p:CdtTrfTxInf/p:PmtId/p:EndToEndId",
    "p:FIToFICstmrCdtTrf/p:CdtTrfTxInf/p:IntrBkSttlmAmt",
    "p:FIToFICstmrCdtTrf/p:CdtTrfTxInf/p:Dbtr",
    "p:FIToFICstmrCdtTrf/p:CdtTrfTxInf/p:Cdtr",
]


def _check_addr(addr_elem: ET.Element, party: str, issues: list) -> None:
    """A structured address must have at least StrtNm or BldgNb, plus Ctry."""
    if addr_elem is None:
        issues.append(f"{party}: missing PstlAdr block")
        return

    has_street  = addr_elem.find("p:StrtNm", NS_MAP) is not None
    has_bldgnb  = addr_elem.find("p:BldgNb", NS_MAP) is not None
    has_country = addr_elem.find("p:Ctry",   NS_MAP) is not None

    if not (has_street or has_bldgnb):
        issues.append(f"{party}: address has neither StrtNm nor BldgNb")
    if not has_country:
        issues.append(f"{party}: address is missing Ctry (ISO country code)")
    else:
        ctry = addr_elem.find("p:Ctry", NS_MAP).text or ""
        if not re.fullmatch(r"[A-Z]{2}", ctry):
            issues.append(f"{party}: country '{ctry}' is not a 2-letter ISO code")


def schema_validate(xml_string: str) -> str:
    """Return 'VALID' on success, or a newline-separated list of issues."""
    issues: list = []

    # ---- 1. Well-formed XML ----
    try:
        root = ET.fromstring(xml_string)
    except ET.ParseError as e:
        return f"INVALID: XML parse error: {e}"

    if root.tag != f"{{{PACS_NS}}}Document":
        issues.append(f"root element is {root.tag}, expected pacs.008 Document")

    # ---- 2. Required structural elements ----
    for path in REQUIRED_ELEMS:
        if root.find(path, NS_MAP) is None:
            issues.append(f"missing required element: {path}")

    # If we don't even have the basic frame, stop here.
    tx = root.find("p:FIToFICstmrCdtTrf/p:CdtTrfTxInf", NS_MAP)
    if tx is None:
        return "INVALID:\n  " + "\n  ".join(issues)

    # ---- 3. EndToEndId non-empty ----
    e2e = tx.find("p:PmtId/p:EndToEndId", NS_MAP)
    if e2e is not None and not (e2e.text or "").strip():
        issues.append("PmtId/EndToEndId is empty")

    # ---- 4. Amount > 0, currency is 3-letter ISO ----
    amt_elem = tx.find("p:IntrBkSttlmAmt", NS_MAP)
    if amt_elem is not None:
        ccy = amt_elem.get("Ccy", "")
        if not re.fullmatch(r"[A-Z]{3}", ccy):
            issues.append(f"IntrBkSttlmAmt @Ccy '{ccy}' is not a 3-letter ISO code")
        try:
            val = float(amt_elem.text or "0")
            if val <= 0:
                issues.append(f"IntrBkSttlmAmt {val} must be > 0")
        except ValueError:
            issues.append(f"IntrBkSttlmAmt '{amt_elem.text}' is not numeric")

    # ---- 5. Per-party address sanity ----
    dbtr_addr = tx.find("p:Dbtr/p:PstlAdr", NS_MAP)
    cdtr_addr = tx.find("p:Cdtr/p:PstlAdr", NS_MAP)
    _check_addr(dbtr_addr, "Dbtr (sender)",      issues)
    _check_addr(cdtr_addr, "Cdtr (beneficiary)", issues)

    if issues:
        return "INVALID:\n  " + "\n  ".join(issues)
    return "VALID"
