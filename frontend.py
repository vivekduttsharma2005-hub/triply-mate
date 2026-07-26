import os
import json
import time
from datetime import datetime

import streamlit as st
from langchain_core.messages import HumanMessage
from main import app

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
#MainMenu, footer, header { visibility: hidden; }

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
if "collected" not in st.session_state:
    st.session_state.collected = None
if "user_query" not in st.session_state:
    st.session_state.user_query = ""
if "history" not in st.session_state:
    st.session_state.history = []  # list of {query, timestamp, filename}
if "quick_fill" not in st.session_state:
    st.session_state.quick_fill = ""
if "trip_meta" not in st.session_state:
    st.session_state.trip_meta = {}

SAVE_DIR = os.path.join(os.path.dirname(__file__), "travel_plans")
os.makedirs(SAVE_DIR, exist_ok=True)

AGENT_META = {
    "flight_agent":    ("✈️", "Flight Agent", "Searching flights..."),
    "hotel_agent":     ("🏨", "Hotel Agent", "Finding hotels..."),
    "itinerary_agent": ("🗓️", "Itinerary Agent", "Building itinerary..."),
    "final_agent":     ("🧠", "Final Agent", "Finalizing plan..."),
}
AGENT_ORDER = ["flight_agent", "hotel_agent", "itinerary_agent", "final_agent"]

# ══════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("<div class='sidebar-title'>🌍 AI Travel Planner</div>", unsafe_allow_html=True)
    st.markdown("---")

    thread_id = st.text_input(
        "👤 User ID", value="vivek_user",
        help="Your session ID — keeps travel history across queries",
    )

    with st.expander("⚙️ Trip Preferences", expanded=False):
        budget = st.selectbox("Budget style", ["No preference", "Budget", "Mid-range", "Luxury"], index=0)
        travelers = st.number_input("Travelers", min_value=1, max_value=20, value=1, step=1)
        currency = st.selectbox("Currency", ["INR (₹)", "USD ($)", "EUR (€)", "GBP (£)"], index=0)

    st.markdown("<div class='sidebar-title'>Powered by</div>", unsafe_allow_html=True)
    for tech in ["🔗 LangGraph", "🧠 Groq · LLaMA 3.3 70B", "🐘 PostgreSQL", "🔍 Tavily Search", "✈️ AviationStack"]:
        st.markdown(f"<div class='sidebar-chip'>{tech}</div>", unsafe_allow_html=True)

    st.markdown("<div class='sidebar-title'>Agent Pipeline</div>", unsafe_allow_html=True)
    for step in ["① Flight Agent", "② Hotel Agent", "③ Itinerary Agent", "④ Final Agent"]:
        st.markdown(f"<div class='sidebar-chip'>{step}</div>", unsafe_allow_html=True)

    if st.session_state.history:
        st.markdown("<div class='sidebar-title'>🕒 Recent Trips</div>", unsafe_allow_html=True)
        for i, h in enumerate(reversed(st.session_state.history[-8:])):
            st.markdown(
                f"<div class='history-item'>📌 {h['query'][:42]}{'...' if len(h['query'])>42 else ''}"
                f"<br><span style='opacity:0.6;font-size:0.72rem'>{h['timestamp']}</span></div>",
                unsafe_allow_html=True,
            )

    st.markdown("---")
    if st.button("🗑️ Clear current results", use_container_width=True):
        st.session_state.collected = None
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════
# HERO
# ══════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="hero-wrapper">
    <img class="hero-bg" src="https://images.unsplash.com/photo-1436491865332-7a61a109cc05?w=1400&q=80" alt="airplane above clouds"/>
    <div class="hero-content">
        <div class="hero-badge">✦ Multi-Agent AI System</div>
        <div class="hero-title">✈️ AI Travel Booking System</div>
        <div class="hero-sub">Four specialized agents work together — searching flights, hotels, building an itinerary, and delivering your perfect trip plan.</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════
# DESTINATION STRIP
# ══════════════════════════════════════════════════════════════════════════
DESTINATIONS = [
    ("🇯🇵 Tokyo",   "https://images.unsplash.com/photo-1540959733332-eab4deabeeaf?w=300&q=70", "7-day Japan trip covering Tokyo and Kyoto"),
    ("🇫🇷 Paris",   "https://images.unsplash.com/photo-1502602898657-3e91760cbb34?w=300&q=70", "5-day romantic Paris getaway"),
    ("🇹🇭 Bangkok", "https://images.unsplash.com/photo-1508009603885-50cf7c579365?w=300&q=70", "6-day Bangkok and Pattaya trip"),
    ("🇮🇹 Rome",    "https://images.unsplash.com/photo-1552832230-c0197dd311b5?w=300&q=70", "7-day Italy trip: Rome, Florence, Venice"),
    ("🇦🇪 Dubai",   "https://images.unsplash.com/photo-1512453979798-5ea266f8880c?w=300&q=70", "4-day Dubai weekend trip"),
]

cols = st.columns(5)
for col, (name, img_url, preset_query) in zip(cols, DESTINATIONS):
    with col:
        st.markdown(f"""
        <div class="dest-card">
            <img src="{img_url}" style="width:100%;height:100%;object-fit:cover;filter:brightness(0.55);" />
            <div style="position:absolute;bottom:8px;left:0;right:0;text-align:center;color:#fff;font-size:0.8rem;font-weight:600;">{name}</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Plan this", key=f"dest_{name}", use_container_width=True):
            st.session_state.quick_fill = preset_query

st.markdown("<br>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════
# QUERY INPUT
# ══════════════════════════════════════════════════════════════════════════
st.markdown("<div class='input-label'>🗺️ Describe your trip</div>", unsafe_allow_html=True)

QUICK = ["7-day Japan under ₹2L", "Paris trip for 5 days", "Dubai weekend trip", "Bali backpacking 10 days"]
qcols = st.columns(len(QUICK))
for qc, label in zip(qcols, QUICK):
    with qc:
        if st.button(label, key=f"q_{label}", use_container_width=True):
            st.session_state.quick_fill = label

user_query = st.text_area(
    "trip_description",
    value=st.session_state.quick_fill,
    placeholder="e.g. Plan a complete 7-day Japan trip including flights, hotels and sightseeing under ₹2 lakhs",
    height=100,
    label_visibility="collapsed",
    key="query_box",
)

char_count = len(user_query.strip())
st.caption(f"{char_count} characters" + ("" if char_count else " — describe destination, dates/duration, and budget for best results"))

gen_col, clear_col = st.columns([4, 1])
with gen_col:
    generate = st.button("🚀  Generate My Travel Plan", use_container_width=True)
with clear_col:
    if st.button("✖ Clear", use_container_width=True):
        st.session_state.quick_fill = ""
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════
# GENERATION
# ══════════════════════════════════════════════════════════════════════════
if generate:
    if not user_query.strip():
        st.warning("Please describe your trip first.")
    elif len(user_query.strip()) < 8:
        st.warning("That description looks too short — add a destination, duration, or budget.")
    else:
        config = {"configurable": {"thread_id": thread_id}}
        collected = {"flight_results": "", "hotel_results": "",
                     "itinerary": "", "final_response": "", "llm_calls": 0}

        pref_note = []
        if budget != "No preference":
            pref_note.append(f"Budget style: {budget}")
        if travelers > 1:
            pref_note.append(f"Travelers: {travelers}")
        if currency != "INR (₹)":
            pref_note.append(f"Preferred currency: {currency}")
        full_query = user_query.strip()
        if pref_note:
            full_query += "\n\n(" + "; ".join(pref_note) + ")"

        st.markdown("---")
        st.markdown("<div class='sec-head'><span>🤖 Agent Pipeline — Live</span></div>", unsafe_allow_html=True)

        progress = st.progress(0.0, text="Starting agents...")
        error_occurred = False

        try:
            for chunk in app.stream(
                {
                    "messages": [HumanMessage(content=full_query)],
                    "user_query": full_query,
                    "flight_results": "",
                    "hotel_results": "",
                    "itinerary": "",
                    "llm_calls": 0,
                },
                config=config,
                stream_mode="updates",
            ):
                for node_name, state_update in chunk.items():
                    icon, label, working_text = AGENT_META.get(node_name, ("🔧", node_name, "Working..."))

                    with st.status(f"{icon}  {label}", state="running", expanded=True) as status_box:
                        st.caption(working_text)

                        if node_name == "flight_agent":
                            text = state_update.get("flight_results", "")
                            collected["flight_results"] = text
                            st.markdown(text or "_No flight data returned._")

                        elif node_name == "hotel_agent":
                            text = state_update.get("hotel_results", "")
                            collected["hotel_results"] = text
                            st.markdown(text or "_No hotel data returned._")

                        elif node_name == "itinerary_agent":
                            text = state_update.get("itinerary", "")
                            collected["itinerary"] = text
                            st.markdown(text or "_No itinerary generated._")

                        elif node_name == "final_agent":
                            msgs = state_update.get("messages", [])
                            text = msgs[-1].content if msgs else ""
                            collected["final_response"] = text
                            st.markdown(text or "_No final response._")

                        collected["llm_calls"] = state_update.get("llm_calls", collected["llm_calls"])
                        status_box.update(state="complete", expanded=True)

                    if node_name in AGENT_ORDER:
                        progress.progress((AGENT_ORDER.index(node_name) + 1) / len(AGENT_ORDER),
                                           text=f"{label} complete")

            progress.progress(1.0, text="All agents complete ✅")
            time.sleep(0.3)
            progress.empty()

        except Exception as e:
            error_occurred = True
            progress.empty()
            st.error(f"⚠️ Something went wrong while running the agent pipeline: {e}")
            st.info("Try simplifying your query, or check that your backend services (LLM, search, DB) are reachable.")

        if not error_occurred:
            st.session_state.collected = collected
            st.session_state.user_query = user_query.strip()
            st.session_state.trip_meta = {
                "thread_id": thread_id, "budget": budget,
                "travelers": travelers, "currency": currency,
            }

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"travel_plan_{timestamp}.md"
            st.session_state.history.append({
                "query": user_query.strip(),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "filename": filename,
            })

# ══════════════════════════════════════════════════════════════════════════
# RESULTS (persisted via session_state so they survive reruns)
# ══════════════════════════════════════════════════════════════════════════
collected = st.session_state.collected
if collected:
    st.markdown(f"""
    <div class="metric-row">
        <div class="metric-box"><div class="metric-val">4</div><div class="metric-lbl">Agents Run</div></div>
        <div class="metric-box"><div class="metric-val">{collected['llm_calls']}</div><div class="metric-lbl">LLM Calls</div></div>
        <div class="metric-box"><div class="metric-val">✅</div><div class="metric-lbl">Status</div></div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div class='sec-head'><span>📋 Trip Results</span></div>", unsafe_allow_html=True)
    tab_final, tab_flight, tab_hotel, tab_itin = st.tabs(
        ["🧠 Final Plan", "✈️ Flights", "🏨 Hotels", "🗓️ Itinerary"]
    )
    with tab_final:
        if collected["final_response"]:
            st.markdown(f"<div class='final-card'>{collected['final_response']}</div>", unsafe_allow_html=True)
        else:
            st.info("No final plan was generated.")
    with tab_flight:
        st.markdown(collected["flight_results"] or "_No flight data returned._")
    with tab_hotel:
        st.markdown(collected["hotel_results"] or "_No hotel data returned._")
    with tab_itin:
        st.markdown(collected["itinerary"] or "_No itinerary generated._")

    # ── Save / export ──
    query_for_file = st.session_state.user_query
    meta = st.session_state.trip_meta
    timestamp_disp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    filename = st.session_state.history[-1]["filename"] if st.session_state.history else "travel_plan.md"

    file_content = f"""# Travel Plan
**Query:** {query_for_file}
**Generated:** {timestamp_disp}
**User ID:** {meta.get('thread_id', '')}
**Preferences:** Budget={meta.get('budget','-')}, Travelers={meta.get('travelers','-')}, Currency={meta.get('currency','-')}

---

## ✈️ Flight Information
{collected['flight_results'] or 'N/A'}

---

## 🏨 Hotel Information
{collected['hotel_results'] or 'N/A'}

---

## 🗓️ Itinerary
{collected['itinerary'] or 'N/A'}

---

## 🧠 Final Travel Plan
{collected['final_response'] or 'N/A'}

---
*LLM Calls: {collected['llm_calls']}*
"""
    save_path = os.path.join(SAVE_DIR, filename)
    with open(save_path, "w", encoding="utf-8") as f:
        f.write(file_content)

    json_content = json.dumps({
        "query": query_for_file,
        "generated_at": timestamp_disp,
        "preferences": meta,
        **{k: v for k, v in collected.items()},
    }, indent=2, ensure_ascii=False)

    st.markdown("<div class='sec-head'><span>💾 Save &amp; Export</span></div>", unsafe_allow_html=True)
    dl1, dl2, info_col = st.columns([1, 1, 3])
    with dl1:
        st.download_button("⬇️ Download .md", data=file_content, file_name=filename,
                            mime="text/markdown", use_container_width=True)
    with dl2:
        st.download_button("⬇️ Download .json", data=json_content,
                            file_name=filename.replace(".md", ".json"),
                            mime="application/json", use_container_width=True)
    with info_col:
        st.markdown(f"<div class='save-bar'>📁 Auto-saved → <code>travel_plans/{filename}</code></div>",
                    unsafe_allow_html=True)