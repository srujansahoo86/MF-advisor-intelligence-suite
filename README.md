# FINTELLIGENCE — Mutual Fund Advisor Intelligence Suite

An AI-powered advisor assistant for Kuvera built across three connected pillars: a RAG-based FAQ chatbot, a review intelligence engine, and a voice appointment scheduler — all gated behind a human-in-the-loop MCP approval layer.

**Live demo:** https://mf-advisor-intelligence-suite-1.onrender.com

---

## Architecture

### Three Pillars

| Pillar | Phase | What it does |
|--------|-------|-------------|
| FAQ Chatbot & RAG Engine | Phase 1 | Answers factual questions about mutual fund schemes using official source documents (KIM, SID, factsheets). Refuses investment advice. |
| Review Intelligence & Weekly Pulse | Phase 2 | Processes customer reviews (CSV) into a structured Weekly Pulse (top themes, quotes, action ideas) and a 6-bullet Fee Explainer. |
| Voice Appointment Scheduler | Phase 3 | Handles spoken booking requests, generates `KV-XXXX` booking codes, and deflects PII to a secure link. |

### How the Pillars Connect

```
Phase 2 (Review Intelligence)
    │
    ├── injects Fee Explainer into Phase 1's vector store (ChromaDB)
    └── writes TopTheme to shared SQLite ──► Phase 3 reads it for the greeting
                                                │
Phase 1 (RAG Engine) ◄──────────────────────────┤
    │                                           │
    └── supplies market-context snippets ──►  Phase 4 (MCP email drafts)
                                                │
                              Phase 4 (MCP Orchestrator)
                                  Queues every tool call as PENDING.
                                  No action executes without advisor approval.
                                  Tools: Calendar Hold, Doc Append, Email Draft.
                                                │
                              Phase 5 / API (FastAPI + HTML UI)
                                  Single entry point exposing all pillars.
```

### Shared Foundation (Phase 0)

All phases share a common layer (`src/Phase0_Shared_Foundation/`):

- **`schemas.py`** — typed data contracts (`Answer`, `Booking`, `WeeklyPulse`, `PendingAction`)
- **`persistence.py`** — single SQLite + ChromaDB access layer
- **`guardrails.py`** — centralised safety classifier (refuses investment advice, performance claims, guaranteed-return promises)
- **`pii.py`** — PII redaction (PAN, phone, email) at ingestion and on voice input
- **`config.py`** — env vars, model names, and the 31-URL source manifest

---

## Setup

### Prerequisites

- Python 3.11+
- A free [Groq API key](https://console.groq.com)

### Install

```bash
git clone <repo-url>
cd "CAPSTONE PROJECT"
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set GROQ_API_KEY=<your-key>
```

### Build the vector store

Place source PDFs in `data/raw_docs/`, then run:

```bash
python -m src.Phase1_FAQ_Chatbot.ingest
```

This indexes all documents into ChromaDB at `data/vectorstore/`.

### Run the server

```bash
uvicorn src.api.main:app --reload --port 8000
```

The API is now available at `http://localhost:8000`.

### Open the UI

Open `stitch_mf_advisor_intelligence_suite/code.html` in a browser. For voice features, serve it over HTTPS (the Web Speech API requires a secure origin).

---

## MCP Tools

Three tools are defined in `src/Phase4_MCP_Orchestration/tools.py`. Every call is queued as `PENDING` and requires explicit advisor approval before executing.

| Tool | What it does |
|------|-------------|
| `Calendar Hold Creator` | Saves a 30-minute advisor calendar slot to SQLite |
| `Doc Append` | Appends the booking summary (code, topic, slot, pulse observation) to `data/shared_notes.md` |
| `Email Draft Generator` | Queries Phase 1 RAG for topic context and drafts a pre-meeting brief for the advisor |

Approve or reject via `POST /api/approve` / `POST /api/reject` (or through the Approval Centre tab in the UI).

---

## Source Manifest

31 official URLs across four source families (Kuvera fund profiles, PPFAS factsheets/KIM/SID, Kuvera help articles, SEBI/AMFI regulatory docs). Full list with per-URL metadata is in `src/Phase0_Shared_Foundation/config.py → Config.SOURCE_MANIFEST`.

The `/api/sources` endpoint returns the complete manifest as JSON.

---

## Running Evals

```bash
python -m src.Phase6_Evals.run_evals
```

Runs 6 evals (3 required, 3 additional). Prints results to stdout and saves `src/Phase6_Evals/eval_report.md`. Exit code 0 = all required evals pass.

| Eval | Type | What it checks |
|------|------|---------------|
| Eval 1: Retrieval Accuracy (RAG) | Required | Faithfulness ≥ 0.8, relevance ≥ 0.8, citation present — 5 golden Q&A pairs |
| Eval 2: Compliance & Safety | Required | 5/5 adversarial prompts refused (advice, PII, guaranteed returns) |
| Eval 3: Tone & Structure | Required | Pulse ≤ 250 words, 3 action ideas, 6 fee bullets, no PII in output |
| Eval 4: MCP Approval Gate | Additional | Tool stays PENDING until approved; rejected tools never execute |
| Eval 5: Integration / E2E | Additional | CSV → Pulse → voice greeting → MCP email → approved → persisted |
| Eval 6: Booking MCP Follow-ups | Additional | All 3 MCP actions queued on booking; approve/reject each independently |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | *(required)* | Groq LLM API key |
| `CHROMA_DB_DIR` | `./data/vectorstore` | ChromaDB persistence directory |
| `SQLITE_DB_PATH` | `./data/app.db` | SQLite database for bookings and approval queue |
| `REVIEWS_CSV_PATH` | `./data/reviews.csv` | Customer reviews file for Phase 2 ingestion |
| `SHARED_NOTES_PATH` | `./data/shared_notes.md` | Advisor notes file written by MCP Doc Append tool |
| `LLM_MODEL` | `llama-3.1-8b-instant` | Groq model name |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | FastEmbed model for ChromaDB |

---

## Project Structure

```
CAPSTONE PROJECT/
├── src/
│   ├── Phase0_Shared_Foundation/   # schemas, persistence, guardrails, pii, config
│   ├── Phase1_FAQ_Chatbot/         # RAG engine + document ingestor
│   ├── Phase2_Review_Intelligence/ # CSV ingestion, Weekly Pulse, Fee Explainer
│   ├── Phase3_Voice_Scheduler/     # booking agent, intent parser, slot manager
│   ├── Phase4_MCP_Orchestration/   # tool definitions + approval orchestrator
│   ├── Phase6_Evals/               # eval suite + eval_report.md
│   ├── Phase7_Deployment/          # smoke test for the live URL
│   ├── api/                        # FastAPI app (main.py)
│   └── tests_integration/          # end-to-end integration tests
├── stitch_mf_advisor_intelligence_suite/   # Phase 5 companion UI (HTML)
├── data/
│   ├── raw_docs/                   # source PDFs (not committed)
│   ├── vectorstore/                # ChromaDB index (committed for deployment)
│   └── reviews.csv                 # sample customer reviews
├── Docs/
│   ├── MF_Advisor_Architecture_v2.md
│   └── sample_voice_transcript.md
├── requirements.txt
├── Procfile                        # for Render deployment
└── .env.example
```
