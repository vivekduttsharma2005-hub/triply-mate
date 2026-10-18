# ✈️ Triply Mate — AI Travel Planner

[![tests](https://github.com/vivekduttsharma2005-hub/triply-mate/actions/workflows/tests.yml/badge.svg)](https://github.com/vivekduttsharma2005-hub/triply-mate/actions/workflows/tests.yml)
[![Live demo](https://img.shields.io/badge/live%20demo-Render-46E3B7?logo=render&logoColor=white)](https://triply-mate-1.onrender.com)
![LangGraph](https://img.shields.io/badge/LangGraph-agents-1C3C3C)
![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688?logo=fastapi&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-UI-FF4B4B?logo=streamlit&logoColor=white)
![License: MIT](https://img.shields.io/badge/license-MIT-blue)

Describe a trip in plain language. A LangGraph pipeline finds flights and hotels **in parallel**, builds an itinerary, **checks the cost against your budget** (and looks for cheaper hotels if it's over), and **asks you a question** if something important is missing, instead of guessing.

### 🔗 Live demo: **https://triply-mate-1.onrender.com**

> Free hosting sleeps when idle, so the first load can take about 50 seconds. After that it responds normally.

**Try prompts like:**
- `5 days in Goa from Jaipur, budget ₹40,000, 2 travelers`
- `Weekend trip to Manali from Delhi under ₹15,000`
- `Plan a trip to Udaipur` → the agent will ask for your origin and number of days
- Follow-up in the same session: `make it cheaper`

---

## Table of contents
- [Architecture](#architecture)
- [What's real and what's estimated](#whats-real-and-whats-estimated)
- [Features](#features)
- [Tech stack](#tech-stack)
- [Evaluation](#evaluation)
- [Setup](#setup)
- [Docker](#docker)
- [Deploy on Render](#deploy-on-render)
- [Observability](#observability-what-is-and-is-not-here)
- [Known limitations](#known-limitations)
- [Roadmap](#roadmap)

---

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
- **Structured output:** every agent returns a validated Pydantic model (`schemas.py`)
- **Parallel agents:** flights and hotels run together
- **Budget loop:** over budget → cheaper hotels, max 2 retries, then an honest "over budget by ₹X" warning
- **Human-in-the-loop:** missing origin / destination / days → the graph pauses, asks, resumes
- **Memory:** Postgres checkpointer keyed by `thread_id`; follow-ups like "make it cheaper" see the previous trip
- **FastAPI backend + Streamlit UI**, `pytest` suite, Docker, GitHub Actions CI
- **Observability:** per-node timings, LLM-call and token counts, optional Langfuse tracing

## Tech stack

| Layer | Tools |
|---|---|
| Orchestration | LangGraph (parallel nodes, conditional edges, interrupt/resume, checkpointing) |
| LLM | Groq (`openai/gpt-oss-120b` by default) with Pydantic structured output |
| Data / tools | Tavily, AviationStack, Open-Meteo, `airportsdata` |
| Backend / UI | FastAPI, Streamlit |
| Memory | PostgreSQL checkpointer (falls back to in-memory) |
| Quality / ops | pytest, GitHub Actions, Docker, Render, optional Langfuse |

## Evaluation

LLM apps are easy to demo and hard to trust, so Triply Mate ships with a repeatable evaluation harness instead of "it looked fine when I tried it."

**The suite:** 20 prompts in `eval/cases.json`, covering easy trips, hard multi-constraint trips, impossible budgets, typos, missing information, group travel, and no budget at all.

**Strict pass criteria.** A case passes only if **all** of these hold:

| Check | What it verifies |
|---|---|
| Budget | Total cost ≤ budget (by estimate) |
| Itinerary length | Correct number of days |
| Completeness | Flights and hotels exist, and nothing is missing from the cost estimate |
| Honesty | Impossible budgets pass **only** if the plan openly says it is over budget |
| Clarification | "Missing info" cases pass **only** if the agent asks the right question instead of guessing |

This closes the usual loophole where a plan "fits the budget" only because flights, hotels or activities were quietly left out. Each run records **pass rate and average latency**, and an optional LLM judge (`--judge`) adds a rough quality score.

```bash
python eval/run_eval.py --label "Improved" --sleep 5 --update-readme
```

`--update-readme` writes the **measured** numbers into the table below (nothing is typed by hand).

<!-- EVAL:START -->
| Version | Model | Pass rate | Avg latency | Date |
|---|---|---|---|---|
| Improved | openai/gpt-oss-120b | 3 / 3 | 37.9 s | 2026-10-18 |
<!-- EVAL:END -->

_The row above is a quick **3-case run** out of the 20-case suite. Rerun the command above for a full result._

_Fares are LLM estimates, so "within budget" means within budget **by estimate**. A case also fails if it only fits the budget because activities, flights or hotels were left out. The optional `--judge` score comes from an LLM and is only a rough signal._

## Setup

```bash
git clone https://github.com/vivekduttsharma2005-hub/triply-mate.git && cd triply-mate
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file (never commit it):
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

**Run (UI only, agents run in-process)** → http://localhost:8501
```bash
streamlit run frontend.py
```

**Run as two services**
```bash
uvicorn api:app --port 8000
TRIPLY_API_URL=http://localhost:8000 streamlit run frontend.py
```

**Tests:** `pytest -q`

**Docker:** see the [Docker](#docker) section below.

## Docker

The repo includes a `Dockerfile`, so the app runs the same on any machine without installing Python or dependencies by hand.

```bash
# build the image
docker build -t triply-mate .

# run it, passing your API keys from .env (keys are never baked into the image)
docker run -p 8000:8000 --env-file .env triply-mate
```

The API is then available at http://localhost:8000.

- **Secrets stay out of the image:** keys are injected at runtime with `--env-file`, so the image is safe to share.
- **Same image locally and in the cloud:** what you test in Docker is what gets deployed.
- Add `DATABASE_URL` to `.env` to enable Postgres-backed memory; without it the app falls back to in-memory.

## Deploy on Render
`render.yaml` is included: Render dashboard → **New → Blueprint** → pick this repo → fill the secret values it asks for
(`GROQ_API_KEY`, `TAVILY_API_KEY`, optional `AVIATIONSTACK_API_KEY` and `DATABASE_URL`). The app starts with
`streamlit run frontend.py` and is health-checked at `/_stcore/health`.
Never put keys in the repo; set them in Render's Environment tab.

## Observability: what is and is not here
Multi-agent pipelines fail in quiet ways: a slow node, a retry loop, a ballooning token bill. Triply Mate makes each run inspectable.

**Included (LLMOps basics):**

| Capability | What you get |
|---|---|
| Per-node timing | Logs how long each graph node takes, so you can see which agent is the bottleneck |
| LLM-call and token counts | Per-run totals, so cost and latency regressions show up early |
| Optional Langfuse tracing | Full trace of every run when `LANGFUSE_*` keys are set; off by default |
| Evaluation harness | 20-case suite with strict pass criteria (see [Evaluation](#evaluation)) |
| Offline test suite | 80+ tests (81 passing at last count) with the LLM and tools mocked, so CI needs no secrets and no network |
| CI | GitHub Actions runs the tests on every push |
| Health check | Render monitors `/_stcore/health` |

**Not included:** alerting, dashboards, drift monitoring, or automated incident response. Those would be the next step for production.

## Known limitations
- No fare API: fares are estimates. A real fares source (e.g. Amadeus) is the biggest accuracy upgrade.
- The budget loop only tries cheaper **hotels** (not flights or fewer days).
- Costs assume 1 room per 2 travelers, round-trip fares, and `days − 1` nights.
- AviationStack's free tier is HTTP-only and covers few routes.
- Memory is per `thread_id`; there is no login, so anyone who knows an ID can reuse it.

## Roadmap
- [ ] Real fares API
- [ ] PDF / `.ics` export
- [ ] Auth + per-user history
- [ ] Response caching
- [ ] Larger eval set

## License
MIT
