"""Evaluation harness: runs eval/cases.json through the real graph and reports PASS/FAIL + latency.

    python eval/run_eval.py --label "Parallel + budget loop"            # needs GROQ/TAVILY/AVIATIONSTACK keys
    python eval/run_eval.py --label smoke --limit 3 --sleep 5 --judge
Uses an in-memory checkpointer so it never writes to your production Postgres.
"""
import argparse
import json
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import BaseModel, Field  # noqa: E402

from observability import RunMetrics  # noqa: E402
from service import new_run_input  # noqa: E402

CASES = Path(__file__).with_name("cases.json")


# ── checks ───────────────────────────────────────────────────────────────
def check_budget(state: dict, case: dict) -> bool:
    budget, total = case.get("budget_inr"), state.get("total_cost_inr", 0)
    if budget is None:
        return True
    if case.get("expect_over_budget"):   # impossible budget: the PASS is being honest about it
        return total > budget and "Over budget" in state.get("final_plan", "")
    return total <= budget


def check_days(state: dict, case: dict) -> bool:
    return len((state.get("itinerary") or {}).get("days") or []) == case["days"]


def check_schema(state: dict) -> bool:
    flights = (state.get("flights") or {}).get("options") or []
    hotels = (state.get("hotels") or {}).get("options") or []
    return bool(flights) and bool(hotels) and all(f["is_estimate"] for f in flights)


def check_complete(state: dict) -> bool:
    """A plan that fits the budget only because activities/hotels/flights were left out is NOT a pass."""
    days = (state.get("itinerary") or {}).get("days") or []
    return not (state.get("chosen") or {}).get("missing") and bool(days) and all(d["activities"] for d in days)


class Judgement(BaseModel):
    score: int = Field(ge=1, le=5, description="1 = unrealistic or wrong, 5 = realistic and consistent")
    reason: str


def judge(llm, query: str, plan: str):
    """LLM-as-judge. It is itself an LLM (can be lenient or inconsistent), so report it separately from hard checks."""
    try:
        j = llm.with_structured_output(Judgement).invoke(
            f"Request: {query}\n\nPlan:\n{plan}\n\nScore 1-5 how realistic and internally consistent this travel plan is "
            "(timings, costs vs. destination, no invented facts)."
        )
        return j.score
    except Exception:
        return None


# ── runner ───────────────────────────────────────────────────────────────
def run_case(graph, case: dict, llm=None, use_judge: bool = False) -> dict:
    metrics = RunMetrics()
    cfg = {"configurable": {"thread_id": f"eval-{case['id']}-{uuid.uuid4().hex[:6]}"}, "callbacks": [metrics]}
    res = {"id": case["id"], "kind": case["kind"], "query": case["query"], "passed": False, "checks": {}, "error": None}
    t0 = time.perf_counter()
    try:
        out = graph.invoke(new_run_input(case["query"]), cfg)
    except Exception as e:
        res["error"] = f"{type(e).__name__}: {str(e)[:200]}"
    else:
        interrupts = out.get("__interrupt__")
        if case.get("expect_clarify"):
            q = str(interrupts[0].value) if interrupts else ""
            res["checks"] = {"asked_question": bool(interrupts), "right_question": case["expect_question_contains"] in q}
        elif interrupts:
            res["checks"] = {"asked_unexpected_question": False}
            res["error"] = f"unexpected question: {interrupts[0].value}"
        else:
            res["checks"] = {"budget": check_budget(out, case), "days": check_days(out, case), "schema": check_schema(out), "complete": check_complete(out)}
            if use_judge and llm is not None:
                res["judge_score"] = judge(llm, case["query"], out.get("final_plan", ""))
    res["passed"] = bool(res["checks"]) and all(res["checks"].values()) and not res["error"]
    res["seconds"] = round(time.perf_counter() - t0, 2)
    res.update({k: v for k, v in metrics.summary().items() if k != "seconds"})
    return res


def summarize(results: list, label: str) -> dict:
    n, ok = len(results), sum(r["passed"] for r in results)
    judged = [r["judge_score"] for r in results if r.get("judge_score")]
    return {
        "label": label, "passed": ok, "total": n,
        "avg_seconds": round(sum(r["seconds"] for r in results) / max(n, 1), 1),
        "avg_llm_calls": round(sum(r["llm_calls"] for r in results) / max(n, 1), 1),
        "avg_judge_score": round(sum(judged) / len(judged), 2) if judged else None,
    }


README = Path(__file__).resolve().parent.parent / "README.md"
EVAL_START, EVAL_END = "<!-- EVAL:START -->", "<!-- EVAL:END -->"
EVAL_HEADER = ["| Version | Model | Pass rate | Avg latency | Date |", "|---|---|---|---|---|"]


def update_readme(summary: dict, model: str, path: Path = README, today: str = None) -> bool:
    """Write this run's REAL numbers into the README table between the EVAL markers. Same label = replace the row."""
    text = path.read_text(encoding="utf-8")
    if EVAL_START not in text or EVAL_END not in text:
        return False
    head, rest = text.split(EVAL_START, 1)
    body, tail = rest.split(EVAL_END, 1)
    rows = [l for l in body.strip().splitlines()
            if l.startswith("|") and not l.startswith("| Version") and not l.startswith("|---") and "not run yet" not in l]
    label = summary["label"]
    rows = [r for r in rows if not r.startswith(f"| {label} |")]
    when = today or f"{datetime.now():%Y-%m-%d}"
    rows.append(f"| {label} | {model} | {summary['passed']} / {summary['total']} | {summary['avg_seconds']} s | {when} |")
    path.write_text(head + EVAL_START + "\n" + "\n".join(EVAL_HEADER + rows) + "\n" + EVAL_END + tail, encoding="utf-8")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="run")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--sleep", type=float, default=3.0, help="seconds between cases (Groq free tier rate limits)")
    ap.add_argument("--judge", action="store_true", help="also score plans with an LLM judge")
    ap.add_argument("--update-readme", action="store_true", help="write the real numbers into the README table")
    args = ap.parse_args()

    from langchain_groq import ChatGroq
    from langgraph.checkpoint.memory import InMemorySaver

    import os

    import main as app_main

    llm = ChatGroq(model=os.getenv("GROQ_MODEL", app_main.DEFAULT_MODEL), temperature=0.2, max_retries=3, timeout=60)
    graph = app_main.build_graph(llm, InMemorySaver())
    cases = json.loads(CASES.read_text(encoding="utf-8"))[: args.limit]

    results = []
    for c in cases:
        r = run_case(graph, c, llm, args.judge)
        results.append(r)
        bad = [k for k, v in r["checks"].items() if not v]
        print(f"{r['id']:>2} {'PASS' if r['passed'] else 'FAIL'}  {r['seconds']:>6}s  {r['kind']:<11} {r['query'][:50]}"
              + (f"  failed={bad}" if bad else "") + (f"  error={r['error']}" if r["error"] else ""))
        time.sleep(args.sleep)

    s = summarize(results, args.label)
    out_dir = Path(__file__).with_name("results")
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"{datetime.now():%Y%m%d_%H%M%S}_{args.label.replace(' ', '_')}.json"
    out.write_text(json.dumps({"summary": s, "results": results}, indent=2), encoding="utf-8")
    print(f"\n{s['passed']}/{s['total']} passed · avg {s['avg_seconds']}s · avg {s['avg_llm_calls']} LLM calls"
          + (f" · judge {s['avg_judge_score']}/5" if s["avg_judge_score"] else ""))
    print(f"\n| Version | Pass rate | Avg latency |\n|---|---|---|\n| {s['label']} | {s['passed']} / {s['total']} | {s['avg_seconds']} s |")
    print(f"\nSaved {out}")
    if args.update_readme:
        model = os.getenv("GROQ_MODEL", app_main.DEFAULT_MODEL)
        print("README table updated." if update_readme(s, model) else "README has no EVAL markers; table not updated.")


if __name__ == "__main__":
    main()
