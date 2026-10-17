"""Triply Mate LangGraph app.

START -> parse_query -> clarify (asks the user if something is missing)
      -> [flight_agent || hotel_agent] -> itinerary_agent -> budget_checker
      -> over budget? hotel_retry -> budget_checker (max MAX_RETRIES)   |   done -> final_agent -> END
"""
import math
import os
import re
from datetime import date
from functools import lru_cache, partial
from typing import Optional, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from observability import log, timed
from schemas import FlightResult, HotelResult, Itinerary, TripRequest
from tools.airports import resolve_airport
from tools.flight_tool import search_flights
from tools.tavily_tool import format_results, tavily_search
from tools.weather_tool import forecast

load_dotenv()

# Groq retired llama-3.3-70b-versatile on 2026-08-16. Override with GROQ_MODEL in .env (e.g. qwen/qwen3.6-27b).
DEFAULT_MODEL = "openai/gpt-oss-120b"
MAX_RETRIES = 2
MEMORY_BACKEND = "not initialised"


class TripState(TypedDict, total=False):
    # input
    query: str
    prefs: dict
    # parsed / clarified trip (these persist per thread_id: that is the "memory")
    origin: str
    origin_country: str
    destination: str
    destination_country: str
    origin_iata: str
    dest_iata: str
    days: int
    budget_inr: Optional[int]
    travelers: int
    style: str
    start_date: str
    interests: list
    assumptions: list
    # agent outputs. Parallel agents write DIFFERENT keys, otherwise LangGraph raises a conflict.
    flights: dict
    flight_note: str
    hotels: dict
    hotel_note: str
    hotel_sources: list
    itinerary: dict
    itinerary_note: str
    place_sources: list
    weather: str
    # budget loop
    chosen: dict
    total_cost_inr: int
    retries: int
    final_plan: str


# ───────────────────────── helpers ─────────────────────────
class StructuredCallError(RuntimeError):
    """The LLM could not produce a valid structured answer (bad key, rate limit, malformed tool call...)."""


def structured_call(llm, schema, system: str, prompt: str, attempts: int = 2, required: bool = False):
    """LLM call returning a validated `schema` instance.

    On failure: returns None (optional steps degrade gracefully) or, if `required`, raises StructuredCallError
    with the REAL reason, so the user is never asked a misleading follow-up question.
    """
    runner = llm.with_structured_output(schema)
    last = None
    for i in range(attempts):
        try:
            return runner.invoke([SystemMessage(content=system), HumanMessage(content=prompt)])
        except Exception as e:
            last = e
            log.warning("structured call %s attempt %d failed: %s: %s", schema.__name__, i + 1, type(e).__name__, str(e)[:300])
    if required:
        raise StructuredCallError(f"{type(last).__name__}: {str(last)[:200]}")
    return None


def _parse_int(text) -> Optional[int]:
    m = re.search(r"\d+", str(text).replace(",", ""))
    return int(m.group()) if m else None


def _dedupe_sources(*lists) -> list:
    seen, out = set(), []
    for lst in lists:
        for s in lst or []:
            if s.get("url") and s["url"] not in seen:
                seen.add(s["url"])
                out.append(s)
    return out


def _sources(results: list) -> list:
    return [{"title": r["title"], "url": r["url"]} for r in results if r.get("url")]


def _nights_rooms(state) -> tuple:
    travelers = state.get("travelers") or 1
    return max((state.get("days") or 1) - 1, 1), math.ceil(travelers / 2)


# ───────────────────────── nodes ─────────────────────────
@timed("parse_query")
def parse_query(llm, state):
    prev = {k: state.get(k) for k in ("origin", "destination", "days", "budget_inr", "travelers") if state.get(k)}
    prefs = state.get("prefs") or {}
    system = (
        f"You extract trip details from a travel request. Today is {date.today().isoformat()}. "
        "Never guess: use null for anything the user did not state (null is allowed for every field). "
        "Country fields are 2-letter ISO codes like IN, JP, FR. 2 lakh = 200000 INR. "
        "Fix obvious spelling mistakes in city names."
    )
    prompt = (
        f"Previous trip on this conversation: {prev or 'none'}\n"
        f"UI defaults: home city={prefs.get('origin')}, travelers={prefs.get('travelers')}, style={prefs.get('style')}\n\n"
        f"New message: {state['query']}\n\n"
        "Carry over origin and travelers from the previous trip when the message doesn't mention them. "
        "Carry over destination, days and budget ONLY if the message clearly modifies the previous trip "
        "(e.g. 'make it cheaper', 'extend to 7 days'); a new destination means a NEW trip."
    )
    req = structured_call(llm, TripRequest, system, prompt, required=True)
    return {
        "origin": req.origin_city or prefs.get("origin") or None,
        "origin_country": req.origin_country,
        "destination": req.destination_city,
        "destination_country": req.destination_country,
        "days": req.days,
        "budget_inr": req.budget_inr,
        "travelers": req.travelers or prefs.get("travelers") or 1,
        "style": req.style or prefs.get("style") or None,
        "start_date": req.start_date,
        "interests": req.interests,
        "assumptions": [],
        "retries": 0,
    }


@timed("clarify")
def clarify(llm, state):
    """Human-in-the-loop: pause and ask instead of guessing. Needs a checkpointer + thread_id."""
    updates, assumptions = {}, list(state.get("assumptions") or [])
    if not state.get("destination"):
        updates["destination"] = str(interrupt("Where would you like to go?")).strip()
    if not state.get("origin"):
        updates["origin"] = str(interrupt("Which city will you be travelling from?")).strip()
    if not state.get("days"):
        days = _parse_int(interrupt("How many days is the trip?"))
        if days is None:
            days = _parse_int(interrupt("Please reply with just a number of days, e.g. 5."))
        if days is None:
            days = 3
            assumptions.append("Trip length was not clear, so 3 days is assumed.")
        updates["days"] = max(1, min(days, 60))
    origin = updates.get("origin") or state["origin"]
    destination = updates.get("destination") or state["destination"]
    updates["origin_iata"] = resolve_airport(origin, None if "origin" in updates else state.get("origin_country"))
    updates["dest_iata"] = resolve_airport(
        destination, None if "destination" in updates else state.get("destination_country")
    )
    updates["assumptions"] = assumptions
    return updates


@timed("flight_agent")
def flight_agent(llm, state):
    o, d = state.get("origin_iata"), state.get("dest_iata")
    data = search_flights(o, d)
    system = (
        "You help estimate flight costs. NEVER invent airlines, flight numbers or schedules: an airline may "
        "only be one that appears in the real flight data; if there is none, use 'Various airlines'. "
        "price_inr is YOUR ESTIMATE of a typical round-trip economy fare per person in INR."
    )
    prompt = (
        f"Route: {state['origin']} ({o}) <-> {state['destination']} ({d}), trip of {state['days']} days.\n"
        f"Real flight data: {data['flights'] or 'none found'}\nNote: {data['note']}\n"
        "Return 1-3 options (use the real airlines if any)."
    )
    result = structured_call(llm, FlightResult, system, prompt)
    options = []
    for opt in (result.options if result else []):
        opt.is_estimate = True  # enforced in code: we have no fare source
        opt.from_code, opt.to_code = (o or opt.from_code), (d or opt.to_code)
        opt.basis = "airline from AviationStack, fare estimated" if data["flights"] else "typical fare estimate"
        options.append(opt)
    note = data["note"] if options else data["note"] + " No fare estimate could be produced."
    return {"flights": {"options": [o_.model_dump() for o_ in options]}, "flight_note": note}


def _norm_words(text: str) -> list:
    return re.sub(r"[^a-z0-9 ]", " ", (text or "").lower()).split()


def ground_hotels(options: list, results: list) -> list:
    """Check the LLM's hotel answers against the search results, in code.

    - a hotel whose name isn't in the results is dropped (never invent hotels)
    - a price the model calls 'real' but whose number isn't in the results is relabelled as an estimate
    - source_url is forced to a URL that was actually returned by the search
    """
    corpus = " ".join(f"{r['title']} {r['snippet']}" for r in results)
    words, digits = set(_norm_words(corpus)), corpus.replace(",", "")
    grounded = []
    for o in options:
        toks = [t for t in _norm_words(o.name) if len(t) > 2]
        if not toks or sum(t in words for t in toks) / len(toks) < 0.7:
            log.info("dropping hotel not found in search results: %s", o.name)
            continue
        if not o.is_estimate and str(o.price_per_night_inr) not in digits:
            o.is_estimate = True   # the number is not in the sources, so it is the model's guess
        best = max(results, key=lambda r: sum(t in set(_norm_words(r["title"] + " " + r["snippet"])) for t in toks), default=None)
        o.source_url = best["url"] if best and best.get("url") else None
        grounded.append(o)
    return grounded


def _hotel_search(llm, state, query: str, extra_instruction: str = ""):
    found = tavily_search(query)
    system = (
        "You extract hotel options from web search results. Only use hotels that appear in the results. "
        "If a snippet states a nightly price, convert it to INR and set is_estimate=false and source_url. "
        "Otherwise estimate a realistic INR price per room per night and set is_estimate=true. "
        "Never invent hotel names. Return up to 3 different options when the results support it."
    )
    prompt = f"City: {state['destination']}. Style: {state.get('style') or 'any'}. {extra_instruction}\n\n{format_results(found['results'])}"
    result = structured_call(llm, HotelResult, system, prompt) if found["results"] else None
    if result:
        result.options = ground_hotels(result.options, found["results"])
    note = found["error"] or ("" if result and result.options else "No hotel options could be verified in the search results.")
    return (result.model_dump() if result else {"options": []}), _sources(found["results"]), note


@timed("hotel_agent")
def hotel_agent(llm, state):
    q = f"best {state.get('style') or ''} hotels in {state['destination']} price per night INR".replace("  ", " ")
    hotels, sources, note = _hotel_search(llm, state, q)
    return {"hotels": hotels, "hotel_sources": sources, "hotel_note": note}


def _itinerary_issues(plan, n_days: int) -> list:
    """What is wrong with an itinerary (empty list = fine). Checks content, not just that the schema parsed."""
    if plan is None:
        return ["return a valid itinerary"]
    out = []
    if len(plan.days) != n_days:
        out.append(f"return exactly {n_days} days, numbered 1..{n_days}")
    if any(not d.activities for d in plan.days):
        out.append("every day needs at least 3 specific activities taken from the web results")
    if sum(d.estimated_cost_inr for d in plan.days) <= 0:
        out.append("give a realistic non-zero per-person cost in INR (food, local transport, entry fees) for each day")
    return out


@timed("itinerary_agent")
def itinerary_agent(llm, state):
    n_days = state["days"]
    found = tavily_search(f"top things to do in {state['destination']} {n_days} day itinerary")
    weather = forecast(state["destination"], state.get("start_date"), n_days)
    system = (
        "You are a careful travel planner. Use the web results for real attractions. "
        "estimated_cost_inr is per PERSON per day for food, local transport and entry fees (no flights/hotel). "
        "If a weather forecast is given, put indoor activities on rainy days; if not, don't mention weather. "
        "Group places that are close together on the same day; avoid long cross-region trips in one day. "
        "Day 1 is arrival (keep it light); the last day is departure (keep it light and finish well before a flight home). "
        "Do not mention days of the week: no travel dates are known."
    )
    base = (
        f"Plan exactly {n_days} days in {state['destination']}. Interests: {state.get('interests') or 'general'}. "
        f"Style: {state.get('style') or 'any'}.\nWeather forecast: {weather or 'not available'}\n\n"
        f"Web results:\n{format_results(found['results'])}"
    )
    plan = structured_call(llm, Itinerary, system, base)
    issues = _itinerary_issues(plan, n_days)
    if issues:  # one corrective retry that tells the model exactly what was wrong
        retry = structured_call(llm, Itinerary, system, base + "\n\nIMPORTANT: " + "; ".join(issues) + ".")
        if retry is not None and len(_itinerary_issues(retry, n_days)) <= len(issues):
            plan = retry
    note = found["error"] or ""
    if plan is None:
        return {"itinerary": {"days": []}, "weather": weather or "", "place_sources": [], "itinerary_note": "Itinerary could not be generated."}
    if any(not d.activities for d in plan.days) or sum(d.estimated_cost_inr for d in plan.days) <= 0:
        note = (note + " The itinerary is incomplete (missing activities or costs).").strip()
    if len(plan.days) > n_days:
        plan.days = plan.days[:n_days]
    elif len(plan.days) < n_days:
        note = (note + f" Itinerary has {len(plan.days)} of {n_days} requested days.").strip()
    return {
        "itinerary": plan.model_dump(), "weather": weather or "",
        "place_sources": _sources(found["results"]), "itinerary_note": note,
    }


@timed("budget_checker")
def budget_checker(llm, state):
    nights, rooms = _nights_rooms(state)
    travelers = state.get("travelers") or 1
    flights = (state.get("flights") or {}).get("options") or []
    hotels = (state.get("hotels") or {}).get("options") or []
    days = (state.get("itinerary") or {}).get("days") or []
    flight = min(flights, key=lambda o: o["price_inr"]) if flights else None
    hotel = min(hotels, key=lambda o: o["price_per_night_inr"]) if hotels else None
    breakdown = {
        "flights": flight["price_inr"] * travelers if flight else 0,
        "hotel": hotel["price_per_night_inr"] * nights * rooms if hotel else 0,
        "activities": sum(d["estimated_cost_inr"] for d in days) * travelers,
    }
    breakdown["nights"], breakdown["rooms"] = nights, rooms
    total = breakdown["flights"] + breakdown["hotel"] + breakdown["activities"]
    missing = [name for name, ok in (("flight fares", flight), ("hotel prices", hotel), ("activity and food costs", breakdown["activities"] > 0)) if not ok]
    return {"total_cost_inr": total, "chosen": {"flight": flight, "hotel": hotel, "breakdown": breakdown, "missing": missing}}


def budget_router(state) -> str:
    budget = state.get("budget_inr")
    if not budget:
        return "done"
    if state["total_cost_inr"] > budget and state.get("retries", 0) < MAX_RETRIES:
        return "retry"
    return "done"


@timed("hotel_retry")
def hotel_retry(llm, state):
    """Looks for cheaper hotels. Separate node (not hotel_agent) so the flight/hotel join isn't re-triggered."""
    bd = state["chosen"]["breakdown"]
    room_nights = max(bd["nights"] * bd["rooms"], 1)
    target = max(int((state["budget_inr"] - bd["flights"] - bd["activities"]) / room_nights), 500)
    q = f"cheap budget hotels hostels in {state['destination']} under {target} INR per night"
    hotels, sources, note = _hotel_search(
        llm, state, q, f"CHEAPER options wanted: aim for at most {target} INR per room per night."
    )
    log.info("hotel_retry %d target=%d options=%d", state.get("retries", 0) + 1, target, len(hotels["options"]))
    if not hotels["options"]:  # keep what we had rather than lose the hotels
        hotels, note = state["hotels"], note or "Cheaper hotel search found nothing."
    return {
        "retries": state.get("retries", 0) + 1, "hotels": hotels, "hotel_note": note,
        "hotel_sources": _dedupe_sources(state.get("hotel_sources"), sources),
    }


def over_budget_warning(state) -> Optional[str]:
    budget, total = state.get("budget_inr"), state.get("total_cost_inr", 0)
    if budget and total > budget:
        return (
            f"⚠️ **Over budget:** the cheapest combination I found costs about ₹{total:,}, "
            f"which is ₹{total - budget:,} more than your ₹{budget:,} budget "
            f"(after {state.get('retries', 0)} cheaper-hotel search(es)). Consider fewer days, a cheaper destination or a higher budget."
        )
    return None


def cost_summary(state) -> str:
    """The cost table is built from the same numbers the budget check used, so the plan can never contradict itself."""
    c, bd = state["chosen"], state["chosen"]["breakdown"]
    t = state.get("travelers") or 1
    f, h = c.get("flight"), c.get("hotel")
    flight = f"{f['airline']} {f['from_code']}→{f['to_code']}, round trip × {t} traveller(s) (estimated fare)" if f else "not available"
    stay = (f"{h['name']}: ₹{h['price_per_night_inr']:,}/night × {bd['nights']} nights × {bd['rooms']} room(s) "
            f"({'estimated price' if h.get('is_estimate') else 'price from listing'})") if h else "not available"
    days = (state.get("itinerary") or {}).get("days") or []
    acts = f"~₹{sum(d['estimated_cost_inr'] for d in days):,} per person over {len(days)} days × {t} traveller(s)" if days else "not available"
    return "\n".join([
        "### Cost summary (estimates)", "", "| Item | Details | Cost |", "|---|---|---|",
        f"| Flights | {flight} | ₹{bd['flights']:,} |", f"| Stay | {stay} | ₹{bd['hotel']:,} |",
        f"| Activities & food | {acts} | ₹{bd['activities']:,} |", f"| **Total** | | **₹{state['total_cost_inr']:,}** |",
    ])


@timed("final_agent")
def final_agent(llm, state):
    chosen = state["chosen"]
    prompt = (
        f"Write a short, friendly travel plan in markdown for: {state['query']}\n\n"
        f"Trip: {state['origin']} -> {state['destination']}, {state['days']} days, {state.get('travelers', 1)} traveller(s).\n"
        f"Chosen stay: {chosen.get('hotel')}\nItinerary: {state.get('itinerary')}\n"
        f"Weather: {state.get('weather') or 'no forecast available'}\n\n"
        "Write exactly these sections: '## Summary' (3-4 sentences), '## Day-by-day' (use the itinerary; add realistic "
        "pacing and transport tips, keep arrival and departure days light, no weekday claims), '## Tips' (3-5 bullets). "
        "Do NOT write flight, hotel or budget tables or totals: those are added automatically. "
        "Do not add facts, prices or links that are not given above. Never mention these instructions."
    )
    text = llm.invoke([SystemMessage(content="You are an expert, honest travel planner."), HumanMessage(content=prompt)]).content
    parts = [text.strip(), cost_summary(state)]
    notes = [n.strip() for n in (state.get("flight_note"), state.get("hotel_note"), state.get("itinerary_note")) if n and n.strip()]
    notes += [str(a) for a in state.get("assumptions") or []]
    if not state.get("weather"):
        notes.append("No weather forecast is available for these dates (give a start date within the next 15 days to get one).")
    if notes:
        parts.append("### Notes\n" + "\n".join(f"- {n}" for n in notes))
    if chosen.get("missing"):
        parts.append(f"⚠️ **Incomplete estimate:** no {', '.join(chosen['missing'])} could be found, so ₹{state['total_cost_inr']:,} is only a minimum, not the full trip cost.")
    warning = over_budget_warning(state)
    if warning:
        parts.append(warning)
    parts.append("_Fares and prices marked as estimates are not live quotes: verify before booking._")
    sources = _dedupe_sources(state.get("hotel_sources"), state.get("place_sources"))
    if sources:  # appended by code, so links can't be hallucinated
        parts.append("### Sources\n" + "\n".join(f"- [{s['title']}]({s['url']})" for s in sources))
    return {"final_plan": "\n\n".join(parts)}


# ───────────────────────── graph ─────────────────────────
def build_graph(llm, checkpointer=None):
    b = StateGraph(TripState)
    for name, fn in [
        ("parse_query", parse_query), ("clarify", clarify), ("flight_agent", flight_agent),
        ("hotel_agent", hotel_agent), ("itinerary_agent", itinerary_agent),
        ("budget_checker", budget_checker), ("hotel_retry", hotel_retry), ("final_agent", final_agent),
    ]:
        b.add_node(name, partial(fn, llm))
    b.add_edge(START, "parse_query")
    b.add_edge("parse_query", "clarify")
    b.add_edge("clarify", "flight_agent")      # these two run in parallel
    b.add_edge("clarify", "hotel_agent")
    b.add_edge(["flight_agent", "hotel_agent"], "itinerary_agent")  # waits for both
    b.add_edge("itinerary_agent", "budget_checker")
    b.add_conditional_edges("budget_checker", budget_router, {"retry": "hotel_retry", "done": "final_agent"})
    b.add_edge("hotel_retry", "budget_checker")
    b.add_edge("final_agent", END)
    return b.compile(checkpointer=checkpointer or InMemorySaver())


def make_checkpointer():
    """Postgres if DATABASE_URL works (pooled, so dropped idle connections recover), else in-memory."""
    global MEMORY_BACKEND
    url = os.getenv("DATABASE_URL")
    if url:
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
            from psycopg.rows import dict_row  # PostgresSaver reads rows by column name: dict_row is required
            from psycopg_pool import ConnectionPool

            pool = ConnectionPool(
                conninfo=url, max_size=5, open=True, check=ConnectionPool.check_connection,
                kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
            )
            saver = PostgresSaver(pool)
            saver.setup()
            MEMORY_BACKEND = "postgres"
            return saver
        except Exception as e:
            log.error("Postgres unavailable (%s); falling back to in-memory checkpoints", type(e).__name__)
            MEMORY_BACKEND = "in-memory (postgres unavailable)"
            return InMemorySaver()
    MEMORY_BACKEND = "in-memory (no DATABASE_URL)"
    return InMemorySaver()


@lru_cache(maxsize=1)
def get_graph():
    from langchain_groq import ChatGroq

    llm = ChatGroq(model=os.getenv("GROQ_MODEL", DEFAULT_MODEL), temperature=0.2, max_retries=2, timeout=60)
    return build_graph(llm, make_checkpointer())


if __name__ == "__main__":
    from langgraph.types import Command
    from service import new_run_input, stream_events

    try:
        graph = get_graph()
    except Exception as e:
        raise SystemExit(f"Not configured correctly ({type(e).__name__}). Set GROQ_API_KEY in your .env file.")
    thread = os.getenv("TRIPLY_THREAD", "cli_user")
    payload = new_run_input(input("Enter travel request: "))
    while True:
        pending = None
        for ev in stream_events(graph, payload, thread):
            if ev["type"] == "interrupt":
                pending = ev["question"]
            elif ev["type"] == "node" and ev["node"] == "final_agent":
                print("\n" + ev["update"]["final_plan"])
            elif ev["type"] == "error":
                print("Error:", ev["message"])
        if not pending:
            break
        payload = Command(resume=input(f"{pending} "))
