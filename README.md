# ✈️ Triply Mate — AI Travel Planner

[![tests](https://github.com/vivekduttsharma2005-hub/triply-mate/actions/workflows/tests.yml/badge.svg)](https://github.com/vivekduttsharma2005-hub/triply-mate/actions/workflows/tests.yml)

Describe a trip in plain language. A LangGraph pipeline finds flights and hotels **in parallel**, builds an itinerary, **checks the cost against your budget** (and looks for cheaper hotels if it's over), and **asks you a question** if something important is missing — instead of guessing.

**Live demo:** https://triply-mate.onrender.com _(free hosting sleeps; the first load can take ~50 s)_

## Architecture

```mermaid
flowchart TD
    A[parse_query<br/>structured output] --> B{clarify<br/>missing info?}
    B -- yes --> Q[/ask the user<br/>interrupt + resume/]
    Q --> B
    B -- no --> F[flight_agent]
    B -- no --> H[hotel_agent]
    F --> I[itinerary_agent<br/>+ weather + web search]
    H --> I
    I --> C{budget_checker}
    C -- over budget, retries < 2 --> R[hotel_retry<br/>cheaper hotels]
    R --> C
    C -- within budget, or retries exhausted --> Z[final_agent<br/>+ sources + honest warning]
```

## What's real and what's estimated

| Data | Source | Note |
|---|---|---|
| Airlines / flight status | AviationStack | Free tier covers few routes. **It has no fares.** |
| Flight **fares** | LLM estimate | Always labelled "(estimate)" in the UI and the plan |
| Hotels | Tavily web results | Price taken from the snippet when present, otherwise an estimate (labelled) |
| Attractions, sources | Tavily | Source links are appended by code, never written by the LLM |
| Weather | Open-Meteo | Only when you give a start date within the next 15 days; otherwise omitted, not invented |
| Airport codes | `airportsdata` + a small alias table | |

If a tool fails, the plan says so. No flights, hotels or links are fabricated.

## Features
- **Structured output** — every agent returns a validated Pydantic model (`schemas.py`)
- **Parallel agents** — flights and hotels run together
- **Budget loop** — over budget → cheaper hotels, max 2 retries, then an honest "over budget by ₹X" warning
- **Human-in-the-loop** — missing origin / destination / days → the graph pauses, asks, resumes
- **Memory** — Postgres checkpointer keyed by `thread_id`; follow-ups like "make it cheaper" see the previous trip
- **FastAPI backend + Streamlit UI**, `pytest` suite, Docker, GitHub Actions CI
- **Observability** — per-node timings, LLM-call and token counts, optional Langfuse tracing

## Evaluation

20 prompts in `eval/cases.json` (easy, hard, impossible budgets, typos, missing info, groups, no budget).
A case passes only if: total ≤ budget **and** itinerary has the right number of days **and** flights/hotels exist
(impossible budgets pass only if the plan honestly says it is over budget; "missing info" cases pass only if the agent asks the right question).

```bash
python eval/run_eval.py --label "Parallel + budget loop" --sleep 5
```

| Version | Pass rate | Avg latency |
|---|---|---|
| Original (sequential, free text) | _run on commit `ac85442`_ | _…_ |
| Parallel + budget loop + clarify | _run `eval/run_eval.py`_ | _…_ |

_Fill this table with your own numbers. Fares are LLM estimates, so "within budget" means within budget **by estimate**. The optional `--judge` score comes from an LLM and is only a rough signal._

## Setup

```bash
git clone https://github.com/vivekduttsharma2005-hub/triply-mate.git && cd triply-mate
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

`.env` (never commit it):
```
GROQ_API_KEY=...
GROQ_MODEL=openai/gpt-oss-120b   # optional; Groq retired llama-3.3-70b-versatile in Aug 2026
TAVILY_API_KEY=...
AVIATIONSTACK_API_KEY=...
DATABASE_URL=postgresql://user:password@localhost:5432/langgraph_memory   # optional: falls back to in-memory
# optional
TRIPLY_API_KEY=...        # require x-api-key on the API
LANGFUSE_PUBLIC_KEY=...   LANGFUSE_SECRET_KEY=...
```

Run (UI only, runs the agents in-process) → http://localhost:8501
```bash
streamlit run frontend.py
```
Run as two services:
```bash
uvicorn api:app --port 8000
TRIPLY_API_URL=http://localhost:8000 streamlit run frontend.py
```
Tests: `pytest -q` · Docker: `docker build -t triply-mate . && docker run -p 8000:8000 --env-file .env triply-mate`

## Known limitations
- No fare API: fares are estimates. A real fares source (e.g. Amadeus) is the biggest accuracy upgrade.
- The budget loop only tries cheaper **hotels** (not flights or fewer days).
- Costs assume 1 room per 2 travelers, round-trip fares, and `days − 1` nights.
- AviationStack's free tier is HTTP-only and covers few routes.
- Memory is per `thread_id`; there is no login, so anyone who knows an ID can reuse it.

## Roadmap
- [ ] Real fares API · [ ] PDF / .ics export · [ ] Auth + per-user history · [ ] Response caching · [ ] Larger eval set

MIT License
