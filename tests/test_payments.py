"""
Tests for the payments toolset.

These exercise the three deterministic tools (mt_parser, pacs008_compose,
schema_validate) end-to-end against the sample fixture. The fourth tool,
address_extract, is the LLM-powered one and is tested separately with a
mocked LLM client.
"""

import json
from pathlib import Path

import pytest

from tools.payments.mt_parser       import mt_parser
from tools.payments.pacs008_compose import pacs008_compose
from tools.payments.schema_validate import schema_validate


REPO_ROOT      = Path(__file__).parent.parent
MT_SAMPLE_PATH = REPO_ROOT / "samples" / "mt103_sample.txt"


# ─────────────────────────────────────────────────────────────────
# mt_parser
# ─────────────────────────────────────────────────────────────────

class TestMTParser:
    @pytest.fixture
    def parsed(self):
        return json.loads(mt_parser(MT_SAMPLE_PATH.read_text()))

    def test_currency_extracted(self, parsed):
        assert parsed["currency"] == "USD"

    def test_amount_normalized_to_dot(self, parsed):
        assert parsed["amount"] == "1500.00"

    def test_value_date_iso_formatted(self, parsed):
        assert parsed["value_date"] == "2026-05-26"

    def test_sender_reference(self, parsed):
        assert parsed["sender_reference"] == "REF20260526001"

    def test_sender_account_and_name(self, parsed):
        assert parsed["sender_account"] == "12345678"
        assert parsed["sender_name"]    == "JOHN SMITH"

    def test_sender_address_block_present(self, parsed):
        assert "123 MAIN ST" in parsed["sender_address_block"]
        assert "NEW YORK"   in parsed["sender_address_block"]

    def test_beneficiary_account_and_name(self, parsed):
        assert parsed["beneficiary_account"] == "98765432"
        assert parsed["beneficiary_name"]    == "ACME WIDGETS LTD"

    def test_remittance(self, parsed):
        assert "INVOICE" in parsed["remittance_info"]


# ─────────────────────────────────────────────────────────────────
# pacs008_compose
# ─────────────────────────────────────────────────────────────────

GOLDEN_PAYLOAD = {
    "sender_reference":   "REF20260526001",
    "value_date":         "2026-05-26",
    "currency":           "USD",
    "amount":             "1500.00",
    "sender_name":        "JOHN SMITH",
    "sender_account":     "12345678",
    "sender_address": {
        "building_number": "123",
        "street_name":     "MAIN ST",
        "town_name":       "NEW YORK",
        "postal_code":     "10001",
        "country":         "US",
        "confidence":      0.97,
    },
    "beneficiary_name":    "ACME WIDGETS LTD",
    "beneficiary_account": "98765432",
    "beneficiary_address": {
        "building_number": "17",
        "street_name":     "OLD STREET",
        "town_name":       "LONDON",
        "postal_code":     "EC1V 9HL",
        "country":         "GB",
        "confidence":      0.95,
    },
    "remittance_info":     "INVOICE 2026-0517 OFFICE SUPPLIES",
}


class TestPacs008Compose:
    @pytest.fixture
    def xml(self):
        return pacs008_compose(json.dumps(GOLDEN_PAYLOAD))

    def test_has_pacs008_namespace(self, xml):
        assert 'xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08"' in xml

    def test_end_to_end_id(self, xml):
        assert "<EndToEndId>REF20260526001</EndToEndId>" in xml

    def test_amount_with_currency_attr(self, xml):
        assert '<IntrBkSttlmAmt Ccy="USD">1500.00</IntrBkSttlmAmt>' in xml

    def test_sender_structured_address(self, xml):
        assert "<StrtNm>MAIN ST</StrtNm>" in xml
        assert "<BldgNb>123</BldgNb>" in xml
        assert "<Ctry>US</Ctry>" in xml

    def test_beneficiary_structured_address(self, xml):
        assert "<StrtNm>OLD STREET</StrtNm>" in xml
        assert "<Ctry>GB</Ctry>" in xml

    def test_remittance_info(self, xml):
        assert "INVOICE 2026-0517 OFFICE SUPPLIES" in xml

    def test_invalid_json_returns_error_string(self):
        result = pacs008_compose("not json at all")
        assert result.startswith("Error:")


# ─────────────────────────────────────────────────────────────────
# schema_validate
# ─────────────────────────────────────────────────────────────────

class TestSchemaValidate:
    def test_golden_xml_is_valid(self):
        xml = pacs008_compose(json.dumps(GOLDEN_PAYLOAD))
        assert schema_validate(xml) == "VALID"

    def test_missing_country_fails(self):
        bad = dict(GOLDEN_PAYLOAD)
        bad["sender_address"] = {
            **GOLDEN_PAYLOAD["sender_address"], "country": "",
        }
        result = schema_validate(pacs008_compose(json.dumps(bad)))
        assert "missing Ctry" in result

    def test_bad_currency_code_fails(self):
        bad = dict(GOLDEN_PAYLOAD)
        bad["currency"] = "XX"
        result = schema_validate(pacs008_compose(json.dumps(bad)))
        assert "Ccy" in result

    def test_zero_amount_fails(self):
        bad = dict(GOLDEN_PAYLOAD)
        bad["amount"] = "0.00"
        result = schema_validate(pacs008_compose(json.dumps(bad)))
        assert "must be > 0" in result

    def test_malformed_xml_is_invalid(self):
        assert schema_validate("<not valid xml").startswith("INVALID")


# ─────────────────────────────────────────────────────────────────
# address_extract — LLM-mocked
# ─────────────────────────────────────────────────────────────────

class TestAddressExtractWithMockedLLM:
    """Tests address_extract by monkeypatching the llm() function it imports."""

    def test_us_address_parsed(self, monkeypatch):
        import agent
        mock_response = json.dumps({
            "building_number": "123",
            "street_name":     "MAIN ST",
            "town_name":       "NEW YORK",
            "postal_code":     "10001",
            "country":         "US",
            "confidence":      0.97,
        })
        monkeypatch.setattr(agent, "llm", lambda s, u, **kw: mock_response)

        from tools.payments.address_extract import address_extract
        out = json.loads(address_extract("123 MAIN ST APT 4B\nNEW YORK NY 10001 USA"))

        assert out["country"]         == "US"
        assert out["building_number"] == "123"
        assert out["confidence"]      == 0.97

    def test_empty_input_short_circuits(self):
        from tools.payments.address_extract import address_extract
        out = json.loads(address_extract(""))
        assert out["confidence"] == 0.0
        assert out["country"]    == ""

    def test_malformed_llm_response_returns_low_confidence(self, monkeypatch):
        import agent
        monkeypatch.setattr(agent, "llm", lambda s, u, **kw: "I'm sorry I can't help")

        from tools.payments.address_extract import address_extract
        out = json.loads(address_extract("17 OLD STREET\nLONDON EC1V 9HL UK"))
        assert out["confidence"] == 0.0
