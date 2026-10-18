"""Tests for the eval harness itself (not the model quality; that needs real API keys)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))

from langgraph.checkpoint.memory import InMemorySaver

import main
import run_eval
from conftest import FakeLLM
from schemas import TripRequest


def case(**kw):
    return {"id": 1, "kind": "easy", "query": "x", "days": 3, "budget_inr": 40000, **kw}


def test_cases_file_is_valid_and_mixed():
    cases = json.loads(run_eval.CASES.read_text(encoding="utf-8"))
    assert len(cases) == 20 and len({c["id"] for c in cases}) == 20
    kinds = {c["kind"] for c in cases}
    assert {"easy", "hard", "tiny_budget", "typo", "missing"} <= kinds
    assert all(c.get("expect_clarify") or c.get("days") for c in cases)


def test_passing_case():
    r = run_eval.run_case(main.build_graph(FakeLLM(), InMemorySaver()), case())
    assert r["passed"] and r["checks"] == {"budget": True, "days": True, "schema": True, "complete": True} and r["llm_calls"] >= 0


def test_over_budget_is_a_FAIL_for_a_normal_case_even_with_an_honest_warning():
    g = main.build_graph(FakeLLM(hotel_prices=(90000,)), InMemorySaver())
    r = run_eval.run_case(g, case())
    assert not r["passed"] and r["checks"]["budget"] is False


def test_over_budget_with_warning_is_a_PASS_when_the_budget_is_impossible():
    g = main.build_graph(FakeLLM(hotel_prices=(90000,)), InMemorySaver())
    assert run_eval.run_case(g, case(expect_over_budget=True))["passed"]


def test_expected_clarification():
    llm = FakeLLM(trip=TripRequest(destination_city="Goa", days=3, budget_inr=40000))
    g = main.build_graph(llm, InMemorySaver())
    ok = run_eval.run_case(g, case(expect_clarify=True, expect_question_contains="travelling from"))
    wrong = run_eval.run_case(g, case(expect_clarify=True, expect_question_contains="How many days"))
    assert ok["passed"] and not wrong["passed"]


def test_unexpected_question_fails_a_normal_case():
    g = main.build_graph(FakeLLM(trip=TripRequest(destination_city="Goa", days=3)), InMemorySaver())
    r = run_eval.run_case(g, case())
    assert not r["passed"] and "unexpected question" in r["error"]


def test_crash_is_recorded_not_raised():
    class Boom:
        def invoke(self, *a, **k): raise RuntimeError("rate limited")
    r = run_eval.run_case(Boom(), case())
    assert not r["passed"] and "RuntimeError" in r["error"]


def test_summary_math():
    rs = [{"passed": True, "seconds": 10, "llm_calls": 4}, {"passed": False, "seconds": 20, "llm_calls": 6}]
    s = run_eval.summarize(rs, "v")
    assert (s["passed"], s["total"], s["avg_seconds"], s["avg_llm_calls"]) == (1, 2, 15.0, 5.0)


def test_partial_plan_that_only_fits_the_budget_by_omission_is_a_FAIL():
    from schemas import DayPlan, Itinerary

    class ZeroCost(FakeLLM):
        def with_structured_output(self, schema):
            if schema is Itinerary:
                class R:
                    def invoke(s, m): return Itinerary(days=[DayPlan(day=d, activities=["x"], estimated_cost_inr=0) for d in (1, 2, 3)])
                return R()
            return super().with_structured_output(schema)

    r = run_eval.run_case(main.build_graph(ZeroCost(), InMemorySaver()), case())
    assert r["checks"]["budget"] is True and r["checks"]["complete"] is False and not r["passed"]


README_TEMPLATE = "intro\n<!-- EVAL:START -->\n| Version | Model | Pass rate | Avg latency | Date |\n|---|---|---|---|---|\n| _not run yet_ | | | | |\n<!-- EVAL:END -->\noutro\n"


def test_update_readme_writes_real_numbers_and_keeps_surrounding_text(tmp_path):
    p = tmp_path / "README.md"
    p.write_text(README_TEMPLATE, encoding="utf-8")
    ok = run_eval.update_readme({"label": "Improved", "passed": 17, "total": 20, "avg_seconds": 31.4}, "m/x", p, today="2026-10-18")
    out = p.read_text(encoding="utf-8")
    assert ok and "| Improved | m/x | 17 / 20 | 31.4 s | 2026-10-18 |" in out
    assert "not run yet" not in out and out.startswith("intro") and out.endswith("outro\n")


def test_update_readme_replaces_same_label_and_appends_new_ones(tmp_path):
    p = tmp_path / "README.md"
    p.write_text(README_TEMPLATE, encoding="utf-8")
    run_eval.update_readme({"label": "A", "passed": 10, "total": 20, "avg_seconds": 50.0}, "m", p, today="d1")
    run_eval.update_readme({"label": "B", "passed": 15, "total": 20, "avg_seconds": 40.0}, "m", p, today="d2")
    run_eval.update_readme({"label": "A", "passed": 12, "total": 20, "avg_seconds": 45.0}, "m", p, today="d3")
    out = p.read_text(encoding="utf-8")
    assert out.count("| A |") == 1 and "12 / 20" in out and "10 / 20" not in out and "| B |" in out


def test_update_readme_without_markers_does_nothing(tmp_path):
    p = tmp_path / "README.md"
    p.write_text("no markers here", encoding="utf-8")
    assert run_eval.update_readme({"label": "A", "passed": 1, "total": 2, "avg_seconds": 1.0}, "m", p) is False
    assert p.read_text(encoding="utf-8") == "no markers here"


def test_real_readme_has_the_markers():
    assert run_eval.EVAL_START in run_eval.README.read_text(encoding="utf-8")


def test_render_yaml_is_valid_and_never_contains_secrets():
    import yaml
    cfg = yaml.safe_load((run_eval.README.parent / "render.yaml").read_text(encoding="utf-8"))
    svc = cfg["services"][0]
    assert "streamlit run frontend.py" in svc["startCommand"] and svc["healthCheckPath"] == "/_stcore/health"
    secret_keys = {v["key"] for v in svc["envVars"] if v.get("sync") is False}
    assert {"GROQ_API_KEY", "TAVILY_API_KEY"} <= secret_keys
    assert not any(v.get("value", "").startswith(("gsk_", "tvly-")) for v in svc["envVars"])
