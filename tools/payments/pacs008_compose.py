"""
pacs008_compose.py — deterministic ISO 20022 pacs.008 XML composer.

Takes a JSON payload containing parsed MT fields PLUS the two structured
addresses produced by address_extract, and emits a pacs.008.001.08 fragment
focused on the CdtTrfTxInf (credit transfer transaction information) block.

This is the smallest meaningful slice of the schema — a real production
implementation would also fill in GrpHdr (group header), settlement
instructions, charge bearer, and intermediaries. The point of this module
is to demonstrate the agent pattern with a real, regulator-recognizable
output shape — not to ship a complete payments engine.

Input contract (one JSON string):
{
  "sender_reference":   "...",
  "value_date":         "YYYY-MM-DD",
  "currency":           "USD",
  "amount":             "1500.00",
  "sender_name":        "...",
  "sender_account":     "...",
  "sender_address":     { ... 6 structured fields from address_extract ... },
  "beneficiary_name":   "...",
  "beneficiary_account":"...",
  "beneficiary_address":{ ... 6 structured fields from address_extract ... },
  "remittance_info":    "..."
}
"""

from __future__ import annotations

import json
from xml.sax.saxutils import escape


PACS_NS = "urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08"


def _addr_xml(addr: dict, indent: str) -> str:
    """Render a PstlAdr block from a structured address dict."""
    if not addr:
        return ""

    parts = []
    if addr.get("street_name"):
        parts.append(f"{indent}  <StrtNm>{escape(addr['street_name'])}</StrtNm>")
    if addr.get("building_number"):
        parts.append(f"{indent}  <BldgNb>{escape(addr['building_number'])}</BldgNb>")
    if addr.get("postal_code"):
        parts.append(f"{indent}  <PstCd>{escape(addr['postal_code'])}</PstCd>")
    if addr.get("town_name"):
        parts.append(f"{indent}  <TwnNm>{escape(addr['town_name'])}</TwnNm>")
    if addr.get("country"):
        parts.append(f"{indent}  <Ctry>{escape(addr['country'])}</Ctry>")

    if not parts:
        return ""

    return f"{indent}<PstlAdr>\n" + "\n".join(parts) + f"\n{indent}</PstlAdr>"


def _party_xml(name: str, account: str, addr: dict, party_tag: str,
               account_tag: str, indent: str) -> str:
    """Render Dbtr/Cdtr (with PstlAdr) and the matching account block."""
    name_xml = f"{indent}  <Nm>{escape(name)}</Nm>" if name else ""
    addr_xml = _addr_xml(addr, indent + "  ")

    inner = "\n".join(p for p in [name_xml, addr_xml] if p)
    party = f"{indent}<{party_tag}>\n{inner}\n{indent}</{party_tag}>"

    acct = (
        f"{indent}<{account_tag}>\n"
        f"{indent}  <Id>\n"
        f"{indent}    <Othr>\n"
        f"{indent}      <Id>{escape(account)}</Id>\n"
        f"{indent}    </Othr>\n"
        f"{indent}  </Id>\n"
        f"{indent}</{account_tag}>"
    ) if account else ""

    return party + ("\n" + acct if acct else "")


def pacs008_compose(payment_json: str) -> str:
    """Compose a pacs.008 CdtTrfTxInf XML fragment from a JSON payload."""
    try:
        p = json.loads(payment_json)
    except (json.JSONDecodeError, TypeError) as e:
        return f"Error: invalid JSON input: {e}"

    end_to_end = p.get("sender_reference", "NOTPROVIDED")
    ccy        = p.get("currency",   "")
    amount     = p.get("amount",     "")
    val_date   = p.get("value_date", "")
    remit      = p.get("remittance_info", "")

    dbtr = _party_xml(
        p.get("sender_name", ""),
        p.get("sender_account", ""),
        p.get("sender_address", {}) or {},
        party_tag="Dbtr",
        account_tag="DbtrAcct",
        indent="      ",
    )
    cdtr = _party_xml(
        p.get("beneficiary_name", ""),
        p.get("beneficiary_account", ""),
        p.get("beneficiary_address", {}) or {},
        party_tag="Cdtr",
        account_tag="CdtrAcct",
        indent="      ",
    )

    remit_xml = ""
    if remit:
        remit_xml = (
            "      <RmtInf>\n"
            f"        <Ustrd>{escape(remit)}</Ustrd>\n"
            "      </RmtInf>"
        )

    fragment = f"""<Document xmlns="{PACS_NS}">
  <FIToFICstmrCdtTrf>
    <CdtTrfTxInf>
      <PmtId>
        <EndToEndId>{escape(end_to_end)}</EndToEndId>
      </PmtId>
      <IntrBkSttlmAmt Ccy="{escape(ccy)}">{escape(amount)}</IntrBkSttlmAmt>
      <IntrBkSttlmDt>{escape(val_date)}</IntrBkSttlmDt>
{dbtr}
{cdtr}{('''
''' + remit_xml) if remit_xml else ''}
    </CdtTrfTxInf>
  </FIToFICstmrCdtTrf>
</Document>"""

    return fragment
