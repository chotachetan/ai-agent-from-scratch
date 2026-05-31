"""
tools/payments — ISO 20022 translation toolset.

Four tools convert a legacy SWIFT MT103 free-text message into a
structured ISO 20022 pacs.008 XML fragment, ready for the Nov 2026
structured-address mandate.

Three of four tools are pure Python and deterministic:
  - mt_parser:       tokenize MT fields
  - pacs008_compose: build the XML fragment
  - schema_validate: validate against the schema + invariant audit

Only one tool calls the LLM — address_extract — because parsing
unstructured free-text addresses is the part that actually needs reasoning.
"""

from .mt_parser       import mt_parser
from .address_extract import address_extract
from .pacs008_compose import pacs008_compose
from .schema_validate import schema_validate


TOOLS = {
    "mt_parser":       mt_parser,
    "address_extract": address_extract,
    "pacs008_compose": pacs008_compose,
    "schema_validate": schema_validate,
}

TOOL_DOCS = """
- mt_parser(mt_message): Parse a SWIFT MT103 message into JSON with fields
  like sender_account, sender_name, sender_address_block, amount, currency,
  beneficiary_name, beneficiary_address_block. Input: raw MT103 text.
- address_extract(address_block): Convert a free-text address block (up to 4
  lines, 35 chars each) into structured ISO 20022 fields as JSON: building_number,
  street_name, town_name, postal_code, country, plus a 0.0-1.0 confidence score.
  Input: just the address lines, separated by newlines.
- pacs008_compose(payment_json): Compose a pacs.008 XML fragment from a JSON
  payload containing parsed MT fields and structured addresses. Input: JSON
  string with the parsed payment + structured addresses merged.
- schema_validate(xml_string): Validate the generated XML against pacs.008
  rules and audit that key invariants (amount, currency, parties) survived
  the conversion. Returns 'VALID' or a list of issues. Input: the XML string.
- reason(prompt): No tool — let the LLM think and answer.
"""
