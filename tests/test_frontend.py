"""Headless UI tests: runs the real frontend.py against the real graph with a fake LLM."""
from pathlib import Path

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from streamlit.testing.v1 import AppTest

import main
from conftest import FakeLLM
from schemas import TripRequest

FRONTEND = str(Path(__file__).resolve().parent.parent / "frontend.py")


def app_with(monkeypatch, llm):
    graph = main.build_graph(llm, InMemorySaver())
    monkeypatch.setattr(main, "get_graph", lambda: graph)
    monkeypatch.delenv("TRIPLY_API_URL", raising=False)
    import client
    monkeypatch.setattr(client, "API_URL", "")
    return AppTest.from_file(FRONTEND, default_timeout=30).run()


def click(at, starts):
    next(b for b in at.button if b.label.startswith(starts)).click()
    return at.run()


def test_page_loads_without_error(monkeypatch):
    at = app_with(monkeypatch, FakeLLM())
    assert not at.exception


def test_quick_fill_button_actually_fills_the_text_area(monkeypatch):
    at = app_with(monkeypatch, FakeLLM())
    at.button(key="dest_🇫🇷 Paris").click().run()
    assert at.text_area(key="query_box").value == "5-day romantic Paris getaway"   # was silently ignored before
    click(at, "✖ Clear")
    assert at.text_area(key="query_box").value == ""


def test_each_visitor_gets_their_own_thread_id(monkeypatch):
    a, b = app_with(monkeypatch, FakeLLM()), app_with(monkeypatch, FakeLLM())
    ids = {a.text_input[0].value, b.text_input[0].value}
    assert len(ids) == 2 and all(i.startswith("guest-") for i in ids)


def test_full_run_shows_results_and_exports(monkeypatch):
    at = app_with(monkeypatch, FakeLLM())
    at.text_area(key="query_box").set_value("3 day Goa trip from Jaipur under 40000").run()
    at = click(at, "🚀")
    assert not at.exception and not at.error
    assert at.session_state["collected"]["final_plan"].startswith("# Your plan")
    assert at.session_state["export"]["filename"].endswith(".md")
    assert len(at.tabs) == 5
    assert len(at.session_state["history"]) == 1


def test_missing_info_asks_a_question_then_resumes(monkeypatch):
    llm = FakeLLM(trip=TripRequest(destination_city="Goa", destination_country="IN", days=3, budget_inr=40000))
    at = app_with(monkeypatch, llm)
    at.text_area(key="query_box").set_value("3 day Goa trip under 40000").run()
    at = click(at, "🚀")
    assert at.session_state["pending"] == "Which city will you be travelling from?"
    assert at.session_state["collected"] is None                       # nothing was guessed
    answer = next(t for t in at.text_input if t.label == "Which city will you be travelling from?")
    answer.set_value("Jaipur")          # no .run(): form inputs only send on submit
    click(at, "Continue")
    assert at.session_state["pending"] is None and at.session_state["collected"]["origin"] == "Jaipur"


def test_pipeline_error_is_shown_not_a_stack_trace(monkeypatch):
    at = app_with(monkeypatch, FakeLLM())
    import client
    monkeypatch.setattr(client, "stream_plan", lambda *a, **k: iter([{"type": "error", "message": "boom"}]))
    at.text_area(key="query_box").set_value("3 day Goa trip from Jaipur").run()
    at = click(at, "🚀")
    assert not at.exception and any("boom" in e.value for e in at.error)


def test_llm_output_is_not_injected_as_html(monkeypatch):
    llm = FakeLLM()
    llm.invoke = lambda m: __import__("langchain_core.messages", fromlist=["AIMessage"]).AIMessage(content="<script>alert(1)</script>plan")
    at = app_with(monkeypatch, llm)
    at.text_area(key="query_box").set_value("3 day Goa trip from Jaipur").run()
    at = click(at, "🚀")
    assert not any("<script>" in m.value for m in at.markdown if getattr(m, "allow_html", False))


def test_missing_groq_key_shows_a_clear_error_not_a_traceback(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("TRIPLY_API_URL", raising=False)
    import client
    monkeypatch.setattr(client, "API_URL", "")
    main.get_graph.cache_clear()
    at = AppTest.from_file(FRONTEND, default_timeout=30).run()
    at.text_area(key="query_box").set_value("3 day Goa trip from Jaipur").run()
    at = click(at, "🚀")
    assert not at.exception and any("not configured correctly" in e.value for e in at.error)


def test_incomplete_total_never_shows_a_green_tick(monkeypatch):
    from schemas import DayPlan, Itinerary
    llm = FakeLLM()
    real = llm.with_structured_output
    def patched(schema):
        if schema is Itinerary:
            class R:
                def invoke(s, m): return Itinerary(days=[DayPlan(day=d, activities=["x"], estimated_cost_inr=0) for d in (1, 2, 3)])
            return R()
        return real(schema)
    llm.with_structured_output = patched
    at = app_with(monkeypatch, llm)
    at.text_area(key="query_box").set_value("3 day Goa trip from Jaipur under 40000").run()
    at = click(at, "🚀")
    budget_md = "\n".join(m.value for m in at.markdown)
    assert "Incomplete: no activity and food costs" in budget_md and "✅ Within your" not in budget_md