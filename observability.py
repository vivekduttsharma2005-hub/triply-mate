"""Logging, per-node timing, token/LLM-call counting and optional Langfuse tracing."""
import functools
import logging
import os
import threading
import time

from langchain_core.callbacks import BaseCallbackHandler
from langgraph.errors import GraphBubbleUp  # raised by interrupt(): control flow, not a failure

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("triply")


def timed(name: str):
    """Decorator for graph nodes: logs duration, and logs the traceback if the node crashes."""

    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            t0 = time.perf_counter()
            try:
                return fn(*args, **kwargs)
            except GraphBubbleUp:
                raise
            except Exception:
                log.exception("node=%s failed", name)
                raise
            finally:
                log.info("node=%s seconds=%.2f", name, time.perf_counter() - t0)

        return wrapper

    return deco


class RunMetrics(BaseCallbackHandler):
    """Counts LLM calls and tokens for one run. Thread-safe because flight/hotel run in parallel."""

    def __init__(self):
        self._lock = threading.Lock()
        self.llm_calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self._t0 = time.perf_counter()

    def on_chat_model_start(self, serialized, messages, **kwargs):
        with self._lock:
            self.llm_calls += 1

    def on_llm_end(self, response, **kwargs):
        for gens in response.generations:
            for g in gens:
                usage = getattr(getattr(g, "message", None), "usage_metadata", None) or {}
                with self._lock:
                    self.input_tokens += usage.get("input_tokens", 0)
                    self.output_tokens += usage.get("output_tokens", 0)

    def summary(self) -> dict:
        return {
            "llm_calls": self.llm_calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "seconds": round(time.perf_counter() - self._t0, 2),
        }


def tracing_callbacks() -> list:
    """Langfuse tracing, switched on only when LANGFUSE_* keys exist. Import path differs by SDK version."""
    if not (os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")):
        return []
    try:
        from langfuse.langchain import CallbackHandler  # Langfuse SDK v3
    except ImportError:
        try:
            from langfuse.callback import CallbackHandler  # Langfuse SDK v2
        except ImportError:
            log.warning("LANGFUSE keys set but the langfuse package is not installed; tracing disabled")
            return []
    return [CallbackHandler()]
