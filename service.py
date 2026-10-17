"""One place that runs the graph and turns it into plain-dict events (used by the API, Streamlit, CLI, eval)."""
from typing import Optional

from observability import RunMetrics, log, tracing_callbacks


def new_run_input(query: str, prefs: Optional[dict] = None) -> dict:
    return {"query": query.strip(), "prefs": prefs or {}, "retries": 0}


def _jsonable(obj):
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    return obj if isinstance(obj, (str, int, float, bool, type(None))) else str(obj)


def stream_events(graph, payload, thread_id: str):
    """Yields {"type": "node"|"interrupt"|"error"|"done", ...}. `payload` is a dict, or Command(resume=...)."""
    metrics = RunMetrics()
    config = {"configurable": {"thread_id": thread_id}, "callbacks": [metrics, *tracing_callbacks()]}
    try:
        for chunk in graph.stream(payload, config, stream_mode="updates"):
            for node, update in chunk.items():
                if node == "__interrupt__":
                    yield {"type": "interrupt", "question": str(update[0].value)}
                    return
                yield {"type": "node", "node": node, "update": _jsonable(update or {})}
    except Exception as e:
        log.exception("graph run failed")
        yield {"type": "error", "message": f"{type(e).__name__}: {str(e)[:300]}"}
        return
    summary = metrics.summary()
    log.info("run done thread=%s %s", thread_id, summary)
    yield {"type": "done", "metrics": summary}
