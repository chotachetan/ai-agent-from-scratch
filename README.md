# Build an AI agent from scratch. No frameworks.

> A multi-step planning agent in ~140 lines of Python. Then the same skeleton, pointed at a multi-billion-dollar banking problem.

[![License: MIT](https://img.shields.io/badge/license-MIT-black.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-black.svg)](https://www.python.org)
[![No frameworks](https://img.shields.io/badge/frameworks-none-D4FF3F.svg)](#)

There's a lot of discussion around AI agents, frameworks, MCPs, orchestration layers, and autonomous workflows right now. But learning the fundamentals is still the most important step.

So this repo rewrites the agent loop from first principles — and then uses the same skeleton to solve a real ISO 20022 payments conversion problem ahead of the November 2026 SWIFT CBPR+ structured-address deadline.

**Two truths this repo demonstrates:**

1. An agent is a control loop that calls an LLM. Frameworks are convenience around that idea, not the idea itself.
2. The agent doesn't change when you change domains. Only the tools change.

---

## Quick start

You need Python 3.10+ and [Ollama](https://ollama.com) running locally.

```bash
# 1. install Ollama (macOS shown; see ollama.com for other platforms)
brew install ollama
ollama serve                          # leave running in another terminal

# 2. pull a small model — ~3GB, runs on 16GB RAM
ollama pull gemma4:e2b

# 3. clone + install
git clone https://github.com/chotachetan/ai-agent-from-scratch
cd ai-agent-from-scratch
pip install -r requirements.txt

# 4. run the teaching example
python examples/01_hello_agent.py

# 5. run the banking example
python examples/02_iso20022_demo.py
```

The examples default to `gemma4:e2b`. If it isn't yet available on your Ollama install, `gemma3:4b` is a drop-in replacement. Override at any time with `--model your-model-tag` or `AGENT_MODEL=your-model-tag`.

---

## The agent in five moves

Every agent in this repo (and most in production) follows the same five moves:

| | Move | What happens |
|---|---|---|
| 01 | **Goal** | Receive what the user actually wants, in plain language. |
| 02 | **Plan** | One LLM call decomposes the goal into ordered steps as JSON. |
| 03 | **Execute** | Run one step. Call a tool if needed. Stay deterministic. |
| 04 | **Observe** | Append the result to memory. Make it available downstream. |
| 05 | **Synthesize** | A final LLM call composes a clean answer from observations. |

That's the whole agent. Everything else — frameworks, tooling, orchestration — is plumbing around this.

---

## Architecture: plan-and-execute (not ReAct)

| | ReAct (industry default) | Plan-and-execute (this repo) |
|---|---|---|
| Pattern | Reason · Act · Reason · Act | One plan, then a deterministic loop |
| LLM calls | ~N | ~2, regardless of N |
| Behavior | Flexible, self-correcting, sometimes wanders | Predictable, inspectable, deterministic dispatch |
| Best for | Open-ended exploration | Production workflows, small local models |

Same agent. **Roughly 10× cheaper** on local models.

The full reasoning lives in the [carousel](#the-carousel-strategy-brief). The TL;DR: plan-and-execute is what works for production agents on commodity hardware. ReAct is what works in research demos.

---

## What's in this repo

```
ai-agent-from-scratch/
├── agent.py                    The ~140-line agent: LLM client, planner, executor, loop
├── tools/
│   ├── basics.py               Teaching tools: calculator, current_date, word_count
│   └── payments/               ISO 20022 toolset
│       ├── mt_parser.py           Deterministic SWIFT MT103 tokenizer
│       ├── address_extract.py     LLM-powered free-text → structured address
│       ├── pacs008_compose.py     Deterministic pacs.008 XML composer
│       └── schema_validate.py     XSD-style validation + invariant audit
├── examples/
│   ├── 01_hello_agent.py       Run the teaching agent
│   └── 02_iso20022_demo.py     Run the same agent against an MT103
├── samples/mt103_sample.txt    A realistic MT103 fixture
├── golden/mt103_sample.pacs008.xml   Expected output (byte-matches generated XML)
├── governance/AGENT_CARD.md    The governance-as-code piece
└── tests/                      Unit tests for every tool, no LLM required
```

---

## The teaching example (~5 minutes)

```bash
python examples/01_hello_agent.py
```

You'll see the agent decompose a multi-part question, route each piece to a tool, and synthesize an answer:

```
GOAL: What is 17 * 23 plus today's day-of-month,
      and how many words are in 'agents plan and act'?

PLAN
  1. [calculator      ] Compute 17 * 23
  2. [current_date    ] Get today's date
  3. [calculator      ] Add {step_1} and the day-of-month from {step_2}
  4. [word_count      ] Count words in 'agents plan and act'
  5. [reason          ] Compose the final answer

EXECUTION
  step 1 -> 391
  step 2 -> 2026-05-31
  step 3 -> 422
  step 4 -> 4
  step 5 -> ...

ANSWER
17 × 23 plus today's day-of-month is 422, and the phrase
'agents plan and act' contains 4 words.
```

Read [`agent.py`](agent.py) once. It's short. Three functions and a `for`-loop.

---

## The banking example (the payoff)

```bash
python examples/02_iso20022_demo.py
```

The same `agent.py`, same loop, same planner and executor. Only the tool registry changes:

```python
TOOLS = {
    "mt_parser":       mt_parser,        # deterministic tokenize
    "address_extract": address_extract,  # LLM — fuzzy free text
    "pacs008_compose": pacs008_compose,  # deterministic XML
    "schema_validate": schema_validate,  # XSD + audit
}
```

The agent reads a SWIFT MT103 message from `samples/`, decomposes the conversion into steps, calls each tool in order, and produces a validated ISO 20022 pacs.008 XML fragment.

### Why this matters

By **November 2026**, every cross-border payment on the SWIFT network must carry structured ISO 20022 addresses. Legacy MT messages store addresses as free text (35 chars × 4 lines, no schema). Parsing them into structured fields reliably — at scale, with regulator-grade audit — is a multi-billion-dollar industry deadline.

### Where the LLM earns its keep

Three of four tools are pure Python. Only `address_extract` calls the LLM, because parsing fuzzy free-text addresses is the part that actually needs reasoning. Everything else is deterministic.

This is the architectural lesson: **scope the LLM narrowly to the fuzzy bits. Keep the rest mechanical.**

### Example input/output

**MT103 input** (`samples/mt103_sample.txt`):
```
:50K:/12345678
JOHN SMITH
123 MAIN ST APT 4B
NEW YORK NY 10001 USA
```

**pacs.008 output** (after the agent runs):
```xml
<Dbtr>
  <Nm>JOHN SMITH</Nm>
  <PstlAdr>
    <StrtNm>MAIN ST</StrtNm>
    <BldgNb>123</BldgNb>
    <PstCd>10001</PstCd>
    <TwnNm>NEW YORK</TwnNm>
    <Ctry>US</Ctry>
  </PstlAdr>
</Dbtr>
```

---

## Governance: read this before adapting for your domain

Most "build an agent" tutorials stop at a working demo. That's the easy part.

The hard part is what makes an agent **deployable** inside a regulated organization — model risk, entitlements, runtime guardrails, output audit, kill-switches. None of this requires a framework. All of it requires deliberate engineering.

[`governance/AGENT_CARD.md`](governance/AGENT_CARD.md) is the agent's accountability surface — the document a bank's MRM team, infosec team, or auditor would ask for before letting this agent near a production payments rail. It maps every governance section (Register, Entitle, Validate, Govern, plus the 3-layer guardrail architecture) onto concrete decisions in this codebase.

If you're going to fork this for your domain — payments, claims, KYC, AML triage — fork the agent card too. Governance is plumbing you write once, not a separate workstream.

---

## Tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

The test suite covers every tool. Payments tests use a mocked LLM client so they run offline and deterministically. The generated pacs.008 XML byte-matches the file in `golden/`.

---

## Extending it

| You want to | Change |
|---|---|
| Use a different LLM (Anthropic, OpenAI, vLLM, etc.) | Rewrite the `llm()` function in `agent.py` |
| Add a new domain | Create `tools/<domain>/` with a `TOOLS` dict and `TOOL_DOCS` string |
| Add a tool to an existing domain | Add a `def your_tool(s: str) -> str:` and register it in the `TOOLS` dict |
| Add reflection | After the loop, run one more LLM call asking *"does this answer the goal?"* If no, loop back into planning |
| Persist memory across runs | Write `memory` to SQLite or JSON, keyed by user/session |

---

## The carousel (strategy brief)

This repo accompanies a 10-slide LinkedIn carousel that walks through the architecture in visual form. The carousel teaches the pattern; this repo proves it works.

The carousel ships these ten slides:

1. Build AI agents from scratch. No frameworks.
2. From a single answer to a sequence of moves.
3. Five moves. That is the entire agent.
4. Three commands. Then you're building.
5. Plan first. Then execute.
6. One LLM client. Tools as functions.
7. One call. JSON out.
8. One step. Then the loop closes.
9. The problem banks are stuck on.
10. Clone the loop. Write your tools.

---

## Three things to take with you

1. **A loop, not a framework.** An agent is a control loop that calls an LLM. Frameworks are convenience around that idea — never necessity.
2. **Tools are functions.** The LLM picks a name; your code runs the function. Keep the boundary clean and the rest follows.
3. **Governance is plumbing you write once.** The agent card is the difference between a demo and a deployable system. Write it before you need it.

---

*Agent frameworks are convenience, not necessity. The pattern is the asset.*

**License:** [MIT](LICENSE) · **Author:** [Surya](https://github.com/chotachetan) · *Builder Notes*
