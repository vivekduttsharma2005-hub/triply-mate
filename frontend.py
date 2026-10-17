import html
import json
import os
import uuid
from datetime import datetime

import streamlit as st
import client

# ══════════════════════════════════════════════════════════════════════════
# PAGE CONFIG
# ══════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="AI Travel Booking System",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ══════════════════════════════════════════════════════════════════════════
# STYLES
# ══════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

html, body, .stApp { font-family: 'Inter', sans-serif; background-color: #080d14; }

/* ── Hero ── */
.hero-wrapper { position: relative; border-radius: 20px; overflow: hidden; margin-bottom: 1.5rem; height: 260px; }
.hero-bg { width: 100%; height: 100%; object-fit: cover; display: block; filter: brightness(0.35); position: absolute; top: 0; left: 0; }
.hero-content { position: relative; z-index: 2; height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; padding: 2rem; }
.hero-badge { background: rgba(58,123,213,0.25); border: 1px solid rgba(58,123,213,0.5); color: #7ab8f5 !important; font-size: 0.75rem; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase; padding: 0.3rem 0.9rem; border-radius: 20px; margin-bottom: 0.9rem; display: inline-block; }
.hero-title { font-size: 2.4rem; font-weight: 700; color: #fff; margin: 0 0 0.6rem; line-height: 1.2; }
.hero-sub { color: #94adc8; font-size: 1rem; max-width: 560px; }

/* ── Cards ── */
.input-card { background: #0e1623; border: 1px solid #1e2e44; border-radius: 16px; padding: 1.6rem 1.8rem; margin-bottom: 1.5rem; }
.input-label { color: #7ab8f5; font-size: 0.8rem; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 0.5rem; }

/* ── Destination chips ── */
.dest-row { display: flex; gap: 0.5rem; flex-wrap: wrap; margin: 0.8rem 0 1.2rem; }

/* ── Buttons ── */
div[data-testid="stButton"] > button {
    background: linear-gradient(135deg, #1a6bbf 0%, #0d4a8a 50%, #0a3d75 100%) !important;
    color: #fff !important; border: none !important; border-radius: 12px !important;
    padding: 0.7rem 1.4rem !important; font-weight: 600 !important; letter-spacing: 0.02em !important;
    transition: all 0.25s ease !important;
}
div[data-testid="stButton"] > button:hover {
    box-shadow: 0 0 30px rgba(26,107,191,0.5), 0 4px 16px rgba(0,0,0,0.4) !important;
    transform: translateY(-1px) !important;
}
.stButton { width: 100%; }

/* Secondary / ghost buttons */
button[kind="secondary"] {
    background: #101c2e !important; border: 1px solid #24405f !important; color: #9cc4ea !important;
    box-shadow: none !important;
}

/* ── Status widgets ── */
[data-testid="stStatusWidget"] { background: #0e1a2e !important; border: 1px solid #1e3050 !important; border-radius: 12px !important; }
[data-testid="stStatusWidget"] * { color: #fff !important; }
[data-testid="stStatusWidget"] a { color: #4ea8f0 !important; }

/* ── Section headers ── */
.sec-head { display: flex; align-items: center; gap: 0.6rem; margin: 1.8rem 0 0.75rem; padding-bottom: 0.5rem; border-bottom: 1px solid #1e2e44; }
.sec-head span { font-size: 1.1rem; font-weight: 600; color: #e0edf8; }

/* ── Metrics ── */
.metric-row { display: flex; gap: 1rem; margin: 1.5rem 0; }
.metric-box { flex: 1; background: #0e1623; border: 1px solid #1e2e44; border-radius: 12px; padding: 1rem 1.2rem; text-align: center; }
.metric-val { font-size: 1.8rem; font-weight: 700; color: #4ea8f0; }
.metric-lbl { color: #7aa8cc !important; font-size: 0.78rem; margin-top: 0.2rem; text-transform: uppercase; letter-spacing: 0.08em; }

/* ── Final plan ── */
.final-card { background: linear-gradient(160deg, #0c1a2e 0%, #0a1520 100%); border: 1px solid #1e3a5c; border-left: 4px solid #3a7bd5; border-radius: 14px; padding: 1.8rem; line-height: 1.8; color: #cce0f5; font-size: 0.95rem; }

/* ── Save / info bar ── */
.save-bar { background: #0e1623; border: 1px solid #1e2e44; border-radius: 10px; padding: 0.85rem 1.2rem; color: #8ab8d8 !important; font-size: 0.88rem; margin-top: 0.5rem; }
.save-bar code { color: #7ab8f5 !important; background: #0a1520 !important; }

/* ── Sidebar ── */
section[data-testid="stSidebar"] { background: #090e18 !important; border-right: 1px solid #141f30 !important; }
.sidebar-chip { background: #0e1a2b; border: 1px solid #1a2e44; border-radius: 8px; padding: 0.45rem 0.75rem; margin-bottom: 0.4rem; font-size: 0.83rem; color: #7aa8cc; }
.sidebar-title { color: #e0edf8; font-size: 1rem; font-weight: 600; margin: 1rem 0 0.5rem; }
.history-item { background: #0e1a2b; border: 1px solid #1a2e44; border-radius: 8px; padding: 0.5rem 0.7rem; margin-bottom: 0.4rem; font-size: 0.8rem; color: #a0c4e0; cursor: pointer; }
.history-item:hover { border-color: #3a7bd5; }

/* Hide branding */
#MainMenu, footer { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent; }

/* Textarea */
.stTextArea textarea { background: #0a1520 !important; border: 1px solid #1e2e44 !important; border-radius: 10px !important; color: #e8f4ff !important; font-size: 0.95rem !important; resize: none !important; }
.stTextArea textarea:focus { border-color: #3a7bd5 !important; box-shadow: 0 0 0 2px rgba(58,123,213,0.2) !important; }
.stTextArea textarea::placeholder { color: #4a6a85 !important; }

/* Text input */
input[type="text"], .stTextInput input { background: #0e1a2b !important; border: 1px solid #1a2e44 !important; border-radius: 8px !important; color: #e0edf8 !important; }
input[type="text"]:focus, .stTextInput input:focus { border-color: #3a7bd5 !important; box-shadow: 0 0 0 2px rgba(58,123,213,0.2) !important; }
input[type="text"]::placeholder { color: #3a5570 !important; }

/* Labels */
.stTextInput label, .stTextArea label, .stSelectbox label, .stNumberInput label, .stSlider label {
    color: #7ab8f5 !important; font-size: 0.82rem !important; font-weight: 600 !important; letter-spacing: 0.08em !important;
}

/* Markdown */
.stMarkdown p, .stMarkdown li, .stMarkdown td, .stMarkdown th { color: #cce0f5 !important; }
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3 { color: #e8f4ff !important; }
.stMarkdown code { background: #0e1a2b !important; color: #7ab8f5 !important; padding: 0.15em 0.4em; border-radius: 4px; }

/* Alerts */
.stAlert { background: #0e1a2b !important; border-radius: 10px !important; }
.stAlert p, .stAlert div { color: #e0edf8 !important; }

/* Sidebar text */
section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] label, section[data-testid="stSidebar"] .stMarkdown { color: #a0c4e0 !important; }
section[data-testid="stSidebar"] hr { border-color: #1a2e44 !important; }

/* Download button */
div[data-testid="stDownloadButton"] > button { background: #1a3a5c !important; color: #e8f4ff !important; border: 1px solid #2a5080 !important; border-radius: 10px !important; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] { gap: 6px; background: transparent; }
.stTabs [data-baseweb="tab"] { background: #0e1623; border: 1px solid #1e2e44; border-radius: 8px 8px 0 0; color: #7aa8cc; padding: 0.5rem 1rem; }
.stTabs [aria-selected="true"] { background: #14263d !important; color: #fff !important; border-color: #3a7bd5 !important; }

/* Progress bar */
.stProgress > div > div { background: linear-gradient(90deg, #1a6bbf, #4ea8f0) !important; }

/* Dest cards clickable */
.dest-card { border-radius: 10px; overflow: hidden; position: relative; height: 90px; cursor: pointer; transition: transform 0.2s; }
.dest-card:hover { transform: scale(1.03); }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════════════════
ss = st.session_state
ss.setdefault("collected", None)      # finished trip (dict of everything the agents produced)
ss.setdefault("run_state", {})        # accumulates node outputs for the run in progress
ss.setdefault("pending", None)        # question the graph is waiting for the user to answer
ss.setdefault("export", None)
ss.setdefault("history", [])
ss.setdefault("query_box", "")
ss.setdefault("uid", "guest-" + uuid.uuid4().hex[:8])   # per-visitor memory; the old shared default leaked trips between users

SAVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "travel_plans")

NODE_META = {
    "parse_query": ("🧾", "Understanding your request"),
    "clarify": ("❓", "Checking for missing details"),
    "flight_agent": ("✈️", "Flight Agent"),
    "hotel_agent": ("🏨", "Hotel Agent"),
    "itinerary_agent": ("🗓️", "Itinerary Agent"),
    "budget_checker": ("💰", "Budget Checker"),
    "hotel_retry": ("🔁", "Looking for cheaper hotels"),
    "final_agent": ("🧠", "Final Agent"),
}
EXPECTED_STEPS = 7   # parse, clarify, flight, hotel, itinerary, budget, final (retries add more)


def inr(n) -> str:
    return f"₹{int(n):,}"


def set_query(text: str):
    """on_click callback. Writing to the widget's own key is the only reliable way to change a keyed text_area."""
    st.session_state.query_box = text


def reset_results():
    ss.collected, ss.run_state, ss.pending, ss.export = None, {}, None, None


# ══════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("<div class='sidebar-title'>🌍 AI Travel Planner</div>", unsafe_allow_html=True)
    st.markdown("---")
    thread_id = st.text_input("👤 User ID", value=ss.uid, help="Your session ID. Reuse it later to keep your trip context.")
    with st.expander("⚙️ Trip Preferences", expanded=False):
        home_city = st.text_input("Home city", placeholder="e.g. Jaipur", help="Used as the departure city when you don't mention one")
        budget = st.selectbox("Budget style", ["No preference", "Budget", "Mid-range", "Luxury"], index=0)
        travelers = st.number_input("Travelers", min_value=1, max_value=20, value=1, step=1)
        st.caption("All budgets are in INR (₹).")

    st.markdown("<div class='sidebar-title'>Powered by</div>", unsafe_allow_html=True)
    for tech in ["🔗 LangGraph", "🧠 Groq · gpt-oss-120b", "🐘 PostgreSQL", "🔍 Tavily Search", "✈️ AviationStack", "⛅ Open-Meteo"]:
        st.markdown(f"<div class='sidebar-chip'>{tech}</div>", unsafe_allow_html=True)
    st.markdown("<div class='sidebar-title'>Agent Pipeline</div>", unsafe_allow_html=True)
    for step in ["① Parse + clarify", "② Flights ∥ Hotels (parallel)", "③ Itinerary", "④ Budget check (retry loop)", "⑤ Final plan"]:
        st.markdown(f"<div class='sidebar-chip'>{step}</div>", unsafe_allow_html=True)
    st.caption(f"Backend: {client.mode()}")

    if ss.history:
        st.markdown("<div class='sidebar-title'>🕒 Recent Trips</div>", unsafe_allow_html=True)
        for h in reversed(ss.history[-8:]):
            q = html.escape(h["query"])   # user text goes into raw HTML, so escape it
            st.markdown(
                f"<div class='history-item'>📌 {q[:42]}{'...' if len(q) > 42 else ''}"
                f"<br><span style='opacity:0.6;font-size:0.72rem'>{h['timestamp']}</span></div>",
                unsafe_allow_html=True,
            )
    st.markdown("---")
    st.button("🗑️ Clear current results", use_container_width=True, on_click=reset_results)

# ══════════════════════════════════════════════════════════════════════════
# HERO
# ══════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="hero-wrapper">
<img class="hero-bg" src="https://images.unsplash.com/photo-1436491865332-7a61a109cc05?w=1400&q=80" alt="airplane above clouds"/>
<div class="hero-content">
<div class="hero-badge">✦ Multi-Agent AI System</div>
<div class="hero-title">✈️ AI Travel Booking System</div>
<div class="hero-sub">Agents search flights and hotels in parallel, build an itinerary, check it against your budget, and ask you when something is missing.</div>
</div>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════
# DESTINATION STRIP
# ══════════════════════════════════════════════════════════════════════════
DESTINATIONS = [
    ("🇯🇵 Tokyo", "https://images.unsplash.com/photo-1540959733332-eab4deabeeaf?w=300&q=70", "7-day Japan trip covering Tokyo and Kyoto"),
    ("🇫🇷 Paris", "https://images.unsplash.com/photo-1502602898657-3e91760cbb34?w=300&q=70", "5-day romantic Paris getaway"),
    ("🇹🇭 Bangkok", "https://images.unsplash.com/photo-1508009603885-50cf7c579365?w=300&q=70", "6-day Bangkok and Pattaya trip"),
    ("🇮🇹 Rome", "https://images.unsplash.com/photo-1552832230-c0197dd311b5?w=300&q=70", "7-day Italy trip: Rome, Florence, Venice"),
    ("🇦🇪 Dubai", "https://images.unsplash.com/photo-1512453979798-5ea266f8880c?w=300&q=70", "4-day Dubai weekend trip"),
]
for col, (name, img_url, preset) in zip(st.columns(5), DESTINATIONS):
    with col:
        st.markdown(f"""
<div class="dest-card">
<img src="{img_url}" style="width:100%;height:100%;object-fit:cover;filter:brightness(0.55);" />
<div style="position:absolute;bottom:8px;left:0;right:0;text-align:center;color:#fff;font-size:0.8rem;font-weight:600;">{name}</div>
</div>""", unsafe_allow_html=True)
        st.button("Plan this", key=f"dest_{name}", use_container_width=True, on_click=set_query, args=(preset,))
st.markdown("<br>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════
# QUERY INPUT
# ══════════════════════════════════════════════════════════════════════════
st.markdown("<div class='input-label'>🗺️ Describe your trip</div>", unsafe_allow_html=True)
QUICK = ["5 day Goa trip under ₹40000", "Paris trip for 5 days", "Dubai weekend trip", "Bali backpacking 10 days"]
for qc, label in zip(st.columns(len(QUICK)), QUICK):
    with qc:
        st.button(label, key=f"q_{label}", use_container_width=True, on_click=set_query, args=(label,))

user_query = st.text_area(
    "trip_description", key="query_box", label_visibility="collapsed", height=100,
    placeholder="e.g. 7-day Japan trip from Delhi with flights, hotels and sightseeing under ₹2 lakhs",
)
n_chars = len(user_query.strip())
st.caption(f"{n_chars} characters" + ("" if n_chars else " — describe destination, duration and budget. If something is missing the agents will ask."))

gen_col, clear_col = st.columns([4, 1])
with gen_col:
    generate = st.button("🚀 Generate My Travel Plan", use_container_width=True)
with clear_col:
    st.button("✖ Clear", use_container_width=True, on_click=set_query, args=("",))


# ══════════════════════════════════════════════════════════════════════════
# PIPELINE RUNNER
# ══════════════════════════════════════════════════════════════════════════
def render_node(node: str, upd: dict, state: dict):
    """What each agent shows inside its (collapsed) status box."""
    if node == "parse_query":
        bits = [f"**From:** {upd.get('origin') or '—'}", f"**To:** {upd.get('destination') or '—'}",
                f"**Days:** {upd.get('days') or '—'}", f"**Budget:** {inr(upd['budget_inr']) if upd.get('budget_inr') else 'not given'}",
                f"**Travelers:** {upd.get('travelers', 1)}"]
        st.markdown(" · ".join(bits))
    elif node == "clarify":
        st.markdown(f"Airports: **{upd.get('origin_iata') or '?'} → {upd.get('dest_iata') or '?'}**")
        for a in upd.get("assumptions") or []:
            st.caption(f"ℹ️ {a}")
    elif node == "flight_agent":
        st.markdown(md_flights(upd.get("flights"), upd.get("flight_note")))
    elif node == "hotel_agent":
        st.markdown(md_hotels(upd.get("hotels"), upd.get("hotel_note")))
    elif node == "itinerary_agent":
        st.markdown(md_itinerary(upd.get("itinerary"), upd.get("weather"), upd.get("itinerary_note")))
    elif node == "budget_checker":
        st.markdown(md_budget(upd, state))
    elif node == "hotel_retry":
        st.markdown(f"Over budget, so I searched for cheaper hotels (attempt {upd.get('retries')} of 2).")
        st.markdown(md_hotels(upd.get("hotels"), upd.get("hotel_note")))
    elif node == "final_agent":
        st.markdown("Final plan ready ✅")


def md_flights(f, note) -> str:
    opts = (f or {}).get("options") or []
    if not opts:
        return f"_No flight options. {note or ''}_"
    rows = ["| Airline | Route | Est. round trip / person |", "|---|---|---|"]
    rows += [f"| {o['airline']} | {o['from_code']} → {o['to_code']} | {inr(o['price_inr'])} (estimate) |" for o in opts]
    return "\n".join(rows) + (f"\n\n_{note}_" if note else "")


def md_hotels(h, note) -> str:
    opts = (h or {}).get("options") or []
    if not opts:
        return f"_No hotel options. {note or ''}_"
    rows = ["| Hotel | Area | Per night | |", "|---|---|---|---|"]
    for o in opts:
        link = f"[source]({o['source_url']})" if o.get("source_url") else ""
        rows.append(f"| {o['name']} | {o.get('area') or '—'} | {inr(o['price_per_night_inr'])}{' (estimate)' if o.get('is_estimate') else ''} | {link} |")
    return "\n".join(rows) + (f"\n\n_{note}_" if note else "")


def md_itinerary(it, weather, note) -> str:
    days = (it or {}).get("days") or []
    if not days:
        return f"_No itinerary generated. {note or ''}_"
    out = [f"**Day {d['day']}** (~{inr(d['estimated_cost_inr'])} per person)\n" + "\n".join(f"- {a}" for a in d["activities"]) for d in days]
    if weather:
        out.append("**Forecast**\n```\n" + weather + "\n```")
    return "\n\n".join(out) + (f"\n\n_{note}_" if note else "")


def md_budget(upd: dict, state: dict) -> str:
    chosen = upd.get("chosen") or state.get("chosen") or {}
    bd = chosen.get("breakdown") or {}
    total = upd.get("total_cost_inr", state.get("total_cost_inr", 0))
    rows = ["| Item | Estimated cost |", "|---|---|", f"| Flights | {inr(bd.get('flights', 0))} |",
            f"| Hotel ({bd.get('nights', 0)} nights × {bd.get('rooms', 0)} room) | {inr(bd.get('hotel', 0))} |",
            f"| Activities & food | {inr(bd.get('activities', 0))} |", f"| **Total** | **{inr(total)}** |"]
    budget = state.get("budget_inr")
    verdict = ""
    missing = chosen.get("missing") or []
    if missing:
        verdict = f"\n\n⚠️ Incomplete: no {', '.join(missing)}, so this total is only a minimum."
    elif budget:
        verdict = f"\n\n✅ Within your {inr(budget)} budget." if total <= budget else f"\n\n⚠️ {inr(total - budget)} over your {inr(budget)} budget."
    return "\n".join(rows) + verdict


def process(events):
    """Consume the event stream and render each agent as it finishes. Returns (outcome, payload)."""
    progress = st.progress(0.0, text="Agents working...")
    outcome, done = ("error", "The pipeline ended unexpectedly."), 0
    for ev in events:
        kind = ev["type"]
        if kind == "node":
            node, upd = ev["node"], ev["update"]
            ss.run_state.update(upd)
            icon, label = NODE_META.get(node, ("🔧", node))
            done += 1
            with st.status(f"{icon} {label}", state="complete", expanded=False):
                render_node(node, upd, ss.run_state)
            progress.progress(min(done / EXPECTED_STEPS, 1.0), text=f"{label} complete")
        elif kind == "interrupt":
            outcome = ("interrupt", ev["question"])
        elif kind == "done":
            ss.run_state["_metrics"] = ev["metrics"]
            outcome = ("done", None)
        elif kind == "error":
            outcome = ("error", ev["message"])
    progress.empty()
    return outcome


def finish(outcome, query: str):
    """Act on how a run ended. A question means: remember it and rerun so the answer form shows."""
    kind, payload = outcome
    if kind == "interrupt":
        ss.pending = payload
        st.rerun()
    elif kind == "error":
        ss.pending = None
        st.error(f"⚠️ Something went wrong while running the agents: {payload}")
        st.info("Try again, or simplify the request. If it keeps failing, check that your API keys and services are reachable.")
    else:
        ss.pending = None
        save_result(query)


def build_markdown(c: dict, query: str, stamp: str) -> str:
    return (
        f"# Travel Plan\n\n**Query:** {query}\n\n**Generated:** {stamp}\n\n**User ID:** {thread_id}\n\n---\n\n"
        f"## ✈️ Flights\n\n{md_flights(c.get('flights'), c.get('flight_note'))}\n\n---\n\n"
        f"## 🏨 Hotels\n\n{md_hotels(c.get('hotels'), c.get('hotel_note'))}\n\n---\n\n"
        f"## 🗓️ Itinerary\n\n{md_itinerary(c.get('itinerary'), c.get('weather'), c.get('itinerary_note'))}\n\n---\n\n"
        f"## 💰 Budget\n\n{md_budget(c, c)}\n\n---\n\n## 🧠 Final Travel Plan\n\n{c.get('final_plan') or 'N/A'}\n"
    )


def save_result(query: str):
    """Runs ONCE when a trip finishes (the old code re-wrote the file on every widget click)."""
    c = dict(ss.run_state)
    now = datetime.now()
    filename = f"travel_plan_{now:%Y%m%d_%H%M%S}.md"
    md = build_markdown(c, query, now.strftime("%Y-%m-%d %H:%M:%S"))
    saved = True
    try:
        os.makedirs(SAVE_DIR, exist_ok=True)
        with open(os.path.join(SAVE_DIR, filename), "w", encoding="utf-8") as f:
            f.write(md)
    except OSError:
        saved = False   # read-only/ephemeral hosting: downloads still work
    payload = {k: v for k, v in c.items() if k != "prefs"}
    ss.collected = c
    ss.export = {"filename": filename, "md": md, "saved": saved,
                 "json": json.dumps({"query": query, "generated_at": now.isoformat(), **payload}, indent=2, ensure_ascii=False)}
    ss.history.append({"query": query, "timestamp": now.strftime("%Y-%m-%d %H:%M"), "filename": filename})


# ══════════════════════════════════════════════════════════════════════════
# GENERATION
# ══════════════════════════════════════════════════════════════════════════
if generate:
    q = user_query.strip()
    if not q:
        st.warning("Please describe your trip first.")
    elif len(q) < 8:
        st.warning("That description looks too short — add a destination, duration, or budget.")
    else:
        reset_results()
        ss.last_query = q
        prefs = {"origin": home_city.strip() or None, "travelers": int(travelers) if travelers > 1 else None,
                 "style": None if budget == "No preference" else budget.lower()}
        st.markdown("---")
        st.markdown("<div class='sec-head'><span>🤖 Agent Pipeline — Live</span></div>", unsafe_allow_html=True)
        finish(process(client.stream_plan(q, thread_id, prefs)), q)

# The graph paused to ask something: show the question and resume the same run with the answer.
if ss.pending:
    st.markdown("---")
    st.markdown("<div class='sec-head'><span>🤔 One quick question</span></div>", unsafe_allow_html=True)
    with st.form("answer_form", clear_on_submit=True):
        answer = st.text_input(ss.pending, placeholder="Type your answer")
        submitted = st.form_submit_button("Continue ▶")
    if submitted:
        if not answer.strip():
            st.warning("Please type an answer.")
        else:
            ss.pending = None
            st.markdown("<div class='sec-head'><span>🤖 Agent Pipeline — Live</span></div>", unsafe_allow_html=True)
            finish(process(client.stream_resume(answer.strip(), thread_id)), ss.get("last_query", ""))

# ══════════════════════════════════════════════════════════════════════════
# RESULTS (survive reruns via session_state)
# ══════════════════════════════════════════════════════════════════════════
collected = ss.collected
if collected:
    m = collected.get("_metrics", {})
    st.markdown(f"""
<div class="metric-row">
<div class="metric-box"><div class="metric-val">{m.get('llm_calls', '—')}</div><div class="metric-lbl">LLM Calls</div></div>
<div class="metric-box"><div class="metric-val">{m.get('input_tokens', 0) + m.get('output_tokens', 0):,}</div><div class="metric-lbl">Tokens</div></div>
<div class="metric-box"><div class="metric-val">{m.get('seconds', '—')}s</div><div class="metric-lbl">Total time</div></div>
<div class="metric-box"><div class="metric-val">{collected.get('retries', 0)}</div><div class="metric-lbl">Budget retries</div></div>
</div>""", unsafe_allow_html=True)

    st.markdown("<div class='sec-head'><span>📋 Trip Results</span></div>", unsafe_allow_html=True)
    tab_final, tab_flight, tab_hotel, tab_itin, tab_budget = st.tabs(["🧠 Final Plan", "✈️ Flights", "🏨 Hotels", "🗓️ Itinerary", "💰 Budget"])
    with tab_final:
        if collected.get("final_plan"):
            with st.container(border=True):   # plain markdown: LLM/web text is never injected as raw HTML
                st.markdown(collected["final_plan"])
        else:
            st.info("No final plan was generated.")
    with tab_flight:
        st.markdown(md_flights(collected.get("flights"), collected.get("flight_note")))
    with tab_hotel:
        st.markdown(md_hotels(collected.get("hotels"), collected.get("hotel_note")))
    with tab_itin:
        st.markdown(md_itinerary(collected.get("itinerary"), collected.get("weather"), collected.get("itinerary_note")))
    with tab_budget:
        st.markdown(md_budget(collected, collected))

    exp = ss.export
    if exp:
        st.markdown("<div class='sec-head'><span>💾 Save &amp; Export</span></div>", unsafe_allow_html=True)
        dl1, dl2, info_col = st.columns([1, 1, 3])
        with dl1:
            st.download_button("⬇️ Download .md", data=exp["md"], file_name=exp["filename"], mime="text/markdown", use_container_width=True)
        with dl2:
            st.download_button("⬇️ Download .json", data=exp["json"], file_name=exp["filename"].replace(".md", ".json"),
                               mime="application/json", use_container_width=True)
        with info_col:
            where = f"📁 Saved → <code>travel_plans/{exp['filename']}</code>" if exp["saved"] else "📁 Not saved on the server (read-only); use the download buttons"
            st.markdown(f"<div class='save-bar'>{where}</div>", unsafe_allow_html=True)
