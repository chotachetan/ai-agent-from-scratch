# Agent Card · ISO 20022 Translator

> **Agent ID** `agent.payments.iso20022.v1`
> **Status** Reference / educational. Not production-deployed.
> **Owner** Payments Engineering Lead (designate before deployment)
> **Last reviewed** May 2026

This card is the agent equivalent of a model card. It is what a bank's
Model Risk Management (MRM) team, Information Security team, or auditor
would expect to see before allowing this agent anywhere near a production
payments rail.

It maps every section of a standard agent governance framework
(Register → Entitle → Validate → Govern, plus the 3-layer guardrail
architecture) onto concrete decisions in this codebase.

---

## 1 · Register

| Field | Value |
|---|---|
| **Identity** | `agent.payments.iso20022.v1` |
| **Type** | Non-human service account |
| **Human sponsor** | Payments Engineering Lead |
| **Purpose** | Translate legacy SWIFT MT103 messages into ISO 20022 pacs.008 ahead of the November 2026 structured-address mandate (CBPR+). |
| **In-scope message types** | MT103 (customer credit transfer) |
| **Out of scope** | MT202, MT940, MT950, any settlement or ledger write |
| **Inventory tag** | `payments / message-translation / iso20022-migration` |

---

## 2 · Entitle (least privilege)

| Resource | Access | Notes |
|---|---|---|
| Inbound MT message queue | **Read only** | Cannot acknowledge, delete, or re-queue |
| Staging XML store | **Write only** | Writes draft pacs.008 fragments for human review |
| Core banking ledger | **None** | Hard boundary. Agent has no ledger entitlement. |
| Sanctions / OFAC service | **Read only** | If extended for sanctions screening — not in v1 |
| KYC / customer master | **None** | |
| Secrets / keys | **None** | Agent uses only its scoped service account |

**Mover/leaver behaviour.** When the human sponsor (Payments Engineering Lead)
changes role or leaves, the agent's service account is automatically frozen
until a new sponsor accepts ownership and re-attests the entitlements above.

---

## 3 · Validate (pre-deployment)

Aligns with **OCC SR 11-7 / Federal Reserve Model Risk Management**.

| Validation step | Evidence in this repo |
|---|---|
| Independent code review | Pull request approval required from a reviewer outside the build team |
| Functional testing | `tests/` — unit tests for each tool, integration test against `golden/` |
| Backtesting | Champion-challenger run on a held-out set of historical MT messages, comparing agent output to current deterministic converter and human-cleaned output |
| Failure mode analysis | See § 6 below |
| Documentation | This card + `README.md` + inline docstrings |
| Approval | Sign-off from MRM, Payments Ops, and Compliance before any production traffic |

---

## 4 · Govern (continuous monitoring)

| Signal | What we log | Trigger |
|---|---|---|
| **Address confidence score** | Per-message confidence from `address_extract` | Below 0.85 → human reviewer queue |
| **Schema validation rate** | % of generated XML that passes `schema_validate` | Drop below 99.0% → page on-call |
| **Invariant audit failures** | Amount, currency, or party mismatch vs source MT | Any failure → block release, page on-call |
| **Latency** | End-to-end conversion time per message | p95 > 5s → investigate |
| **LLM call volume** | Calls per message (should be 1: just `address_extract`) | Spike → planner regression |

**Recertification.** Monthly automated review of all metrics. Quarterly
manual re-validation by MRM. Any production model swap (e.g. moving from
gemma3:4b to a larger model) triggers a fresh validation cycle.

---

## 5 · Guardrails (defense-in-depth, outside the model)

### Input filters

- PII redaction layer **before** the LLM call: account numbers and names are
  stripped from the prompt context passed to `address_extract`. Only the
  address lines themselves are sent to the model.
- Prompt-injection scan on free-text fields (`:70:` remittance info,
  address lines) — refuse messages containing instruction-like tokens
  (`ignore previous`, `system:`, etc.).
- Maximum message size: 4 KB (real MT103 is typically under 2 KB).

### Runtime logic

- **Hard rule:** the agent NEVER publishes XML directly. Every output
  lands in a staging store for human or downstream-system review.
- Confidence threshold: addresses with `confidence < 0.85` are flagged and
  routed to human review, never auto-promoted.
- The agent has no tools that can modify, send, or settle a payment.
  Its tool registry contains only: parse, extract, compose, validate.

### Output audit

- `schema_validate` is the last step of every plan. A failure blocks release.
- Invariant audit: amount, currency, sender account, beneficiary account,
  and remittance text must match between the source MT and the generated
  XML byte-for-byte (after normalization). Any mismatch blocks release.
- All generated XML is logged with the source MT for downstream replay.

---

## 6 · Known failure modes

| Mode | Mitigation |
|---|---|
| LLM hallucinates a country code | `schema_validate` rejects non-ISO 3166-1 alpha-2 codes |
| LLM mis-parses a multi-line address | Confidence score routes to human review |
| LLM returns malformed JSON | `address_extract` parses forgivingly + returns zero-confidence default |
| Ollama server unavailable | Caller sees a timeout; no partial XML is emitted |
| MT message contains unsupported field | `mt_parser` returns parsed fields with the unsupported field ignored; the compose step refuses to emit if a required field is missing |

---

## 7 · Compliance anchors

| Domain | Standard | This agent's posture |
|---|---|---|
| Model risk | OCC SR 11-7 | Independent validation, inventory tagging, monthly recertification |
| Data privacy | GLBA, FFIEC | PII redaction before LLM call; no PII logged |
| Payments standards | SWIFT CBPR+, ISO 20022 | The use case itself — Nov 2026 mandate compliance |
| Travel rule | FATF Recommendation 16 | Originator and beneficiary completeness checked in `schema_validate` |
| Operational resilience | DORA, NIST AI RMF | Kill-switch: a single feature flag stops all agent activity; incident response runbook in `governance/INCIDENT_RUNBOOK.md` (TODO before production) |

---

## 8 · Kill-switch

A single environment variable, `AGENT_DISABLED=1`, causes the agent's
`run_agent` function to refuse to execute. Setting this flag stops all
agent activity globally without requiring a code deployment.

In production, this flag is also wired to:

- A pager alert that notifies the on-call engineer when set.
- An automatic ticket to MRM documenting the reason and duration.

---

*This card is the agent's accountability surface. Update it whenever
the agent's tools, entitlements, or sponsor change.*
