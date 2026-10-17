"""FastAPI backend. Streams the agent pipeline as newline-delimited JSON events.

Run:  uvicorn api:app --port 8000
Optional: set TRIPLY_API_KEY and clients must send it as the `x-api-key` header.
"""
import json
import os
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from langgraph.types import Command
from pydantic import BaseModel, Field

from main import get_graph
from service import new_run_input, stream_events

app = FastAPI(title="Triply Mate API", version="1.0")


def require_key(x_api_key: Optional[str] = Header(default=None)):
    expected = os.getenv("TRIPLY_API_KEY")
    if expected and x_api_key != expected:
        raise HTTPException(status_code=401, detail="invalid or missing x-api-key")


class PlanIn(BaseModel):
    query: str = Field(min_length=8, max_length=2000)
    thread_id: str = Field(min_length=1, max_length=100)
    prefs: dict = Field(default_factory=dict)


class ResumeIn(BaseModel):
    answer: str = Field(min_length=1, max_length=500)
    thread_id: str = Field(min_length=1, max_length=100)


def _safe_graph():
    """-> (graph, None) or (None, error_event). A missing GROQ key must not become an opaque HTTP 500."""
    try:
        return get_graph(), None
    except Exception as e:
        return None, {"type": "error", "message": f"Backend is not configured correctly ({type(e).__name__}). Check GROQ_API_KEY and DATABASE_URL."}


def _run(payload, thread_id):
    graph, err = _safe_graph()
    return [err] if err else stream_events(graph, payload, thread_id)


def _ndjson(events):
    return StreamingResponse((json.dumps(e, ensure_ascii=False) + "\n" for e in events), media_type="application/x-ndjson")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/plan", dependencies=[Depends(require_key)])
def plan(body: PlanIn):
    return _ndjson(_run(new_run_input(body.query, body.prefs), body.thread_id))


@app.post("/resume", dependencies=[Depends(require_key)])
def resume(body: ResumeIn):
    return _ndjson(_run(Command(resume=body.answer), body.thread_id))
