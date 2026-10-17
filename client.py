"""What the Streamlit UI talks to. Same event stream whether the graph runs remotely (API) or in-process."""
import json
import os

import httpx

API_URL = (os.getenv("TRIPLY_API_URL") or "").rstrip("/")
_HEADERS = {"x-api-key": os.environ["TRIPLY_API_KEY"]} if os.getenv("TRIPLY_API_KEY") else {}


def mode() -> str:
    return f"API {API_URL}" if API_URL else "in-process"


def _remote(path: str, body: dict):
    try:
        with httpx.stream("POST", f"{API_URL}{path}", json=body, headers=_HEADERS, timeout=httpx.Timeout(10, read=180)) as r:
            if r.status_code != 200:
                yield {"type": "error", "message": f"API returned HTTP {r.status_code}"}
                return
            for line in r.iter_lines():
                if line:
                    yield json.loads(line)
    except httpx.HTTPError as e:
        yield {"type": "error", "message": f"Could not reach the API ({type(e).__name__})."}


def _local_graph():
    """-> (graph, None) or (None, error_event). A missing key must be a readable message, not a traceback."""
    try:
        from main import get_graph

        return get_graph(), None
    except Exception as e:
        return None, {"type": "error", "message": f"Backend is not configured correctly ({type(e).__name__}). Check GROQ_API_KEY and DATABASE_URL."}


def stream_plan(query: str, thread_id: str, prefs: dict):
    if API_URL:
        yield from _remote("/plan", {"query": query, "thread_id": thread_id, "prefs": prefs})
        return
    from service import new_run_input, stream_events

    graph, err = _local_graph()
    yield from ([err] if err else stream_events(graph, new_run_input(query, prefs), thread_id))


def stream_resume(answer: str, thread_id: str):
    if API_URL:
        yield from _remote("/resume", {"answer": answer, "thread_id": thread_id})
        return
    from langgraph.types import Command
    from service import stream_events

    graph, err = _local_graph()
    yield from ([err] if err else stream_events(graph, Command(resume=answer), thread_id))
