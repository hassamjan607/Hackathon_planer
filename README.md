# Mind to Machine Hackathon Planning Agent

A high-performance, deterministic agentic planning system built for the **Mind to Machine Hackathon** (18 November 2026).
Ingests messy real-world communications (emails, WhatsApp messages, and notices in English and Roman Urdu) and plans a 4-hour physical hackathon in Islamabad for 150 students in 50 teams across five areas: **venue, schedule, food, judging, and budget**.

---

## Core Philosophy & Design

* **The Model Reads, Code Decides:** Exactly **1 model call** (`area=reading`) per run to parse messy text into structured facts. All arithmetic, candidate venue ranking, judging scheduling, timeline creation, and budget balance validation are executed in deterministic Python code.
* **Propose, Validate, Commit:** Every change is tested atomically on an isolated clone of the state. If any constraint or invariant fails, the message is **rejected with an explicit mathematical proof** (naming exact figures), and the previous valid plan is preserved.
* **Zero Hardcoding Guarantee:** Strict compliance with Rule 1: No pack facts, hall names, sender names, prices, or numbers exist anywhere in application source code.
* **Single Command Entrypoint:** `python run.py <messages_file>` (default `messages.txt`) automatically detects first-run (`FULL`), update (`UPDATE`), or no-op (`NOOP`) via SHA-1 content hashing.
* **Honest Cumulative Trace:** Model calls are numbered sequentially; rules, repairs, supersessions, and rejections are un-numbered events. Token counts are copied directly from API responses without estimation.

---

## Directory Structure

```text
├── run.py                 # The ONE command entrypoint
├── serve.py               # Optional stdlib web server (HTTP :8000)
├── requirements.txt       # requests, rich
├── .env.example           # LLM config (OpenAI-compatible / Ollama / Fake)
├── config/
│   ├── policy.toml        # Policy defaults (timings, block orders, repair ladder)
│   └── limits.toml        # Execution deadlines and call caps
├── planner/
│   ├── cli.py             # CLI mode detection, flow control, timeout enforcement
│   ├── ingest.py          # Message splitter & SHA-1 hasher
│   ├── llm.py             # Provider adapter (captures exact token usage)
│   ├── schema.py          # Single source of truth for facts & plan field paths
│   ├── prompts.py         # Dynamic prompt generator derived from schema.py
│   ├── reader.py          # ONLY module that calls the model (tag: reading)
│   ├── facts.py           # FactStore (Jaccard name matching, superseding by date)
│   ├── engine.py          # Propose -> plan -> validate -> repair -> commit/reject
│   ├── repair.py          # Downgrade strategies (food std->low, cheaper venue)
│   ├── validator.py       # Six graded checks + generic AST rule evaluator
│   ├── state.py           # Atomic state persistence (state/state.json)
│   ├── areas/             # Pure functional area planners (people, venue, food, judging, schedule, budget)
│   └── render/            # Rich console output & self-contained HTML report
├── tests/
│   ├── fixtures/          # Message packs (.txt) & expected extractions (.json)
│   ├── test_*.py          # 31 unit tests covering all components & edge cases
│   ├── eval_reader.py     # Reader extraction benchmark
│   └── check_anti_hardcode.py # Codebase audit ensuring zero pack facts in code
├── state/                 # Runtime state (git-ignored)
└── out/                   # Final plan.json, trace.txt, trace.json, report.html (git-ignored)
```

---

## Quickstart

### 1. Setup Environment
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# Edit .env with your provider credentials (or leave LLM_PROVIDER=fake for test mode)
```

### 2. Run Planning System
```bash
# Full initial run
python run.py tests/fixtures/sample_pack.txt

# Incremental update (same command, automatically detected)
python run.py tests/fixtures/practice_msg1.txt
```

### 3. Run Verification & Anti-Hardcode Tests
```bash
# Run complete test suite (31 tests)
python -m unittest discover tests

# Verify zero hardcoded facts in source code
python tests/check_anti_hardcode.py
```

### 4. Interactive Report UI
After any run, open `out/report.html` in your browser (works directly via `file://` with no build or internet connection required).
To launch the optional live demo server:
```bash
python serve.py
# Open http://localhost:8000
```
