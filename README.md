# ✈️ Triply Mate — AI Travel Booking System

A multi-agent AI travel planner built with **LangGraph** and **Streamlit**. Describe your trip in plain language, and four specialized agents collaborate to find flights, hotels, build an itinerary, and produce a final travel plan — all in one live pipeline.

## 🚀 Features

- **Multi-agent pipeline** — Flight Agent → Hotel Agent → Itinerary Agent → Final Agent, orchestrated with LangGraph
- **Live agent status UI** — watch each agent work in real time via Streamlit
- **Persistent memory** — conversation/session state stored in Postgres via `langgraph-checkpoint-postgres`, so trip context carries across queries for the same user
- **Web search grounding** — Tavily API for up-to-date travel info
- **Flight data** — AviationStack API, filtered by origin/destination
- **Export** — download the generated plan as Markdown or JSON
- **Trip preferences** — budget style, traveler count, currency

## 🧠 Tech Stack

| Layer | Tech |
|---|---|
| Orchestration | LangGraph |
| LLM | Groq (LLaMA 3.3 70B) via `langchain-groq` |
| Web search | Tavily |
| Flight data | AviationStack |
| Memory/checkpointing | PostgreSQL |
| Frontend | Streamlit |

## 📁 Project Structure

```
triply-mate/
├── frontend.py          # Streamlit UI
├── main.py               # LangGraph app definition (agent graph)
├── tools/
│   ├── flight_tool.py     # AviationStack flight search
│   └── tavily_tool.py     # Tavily web search
├── requirements.txt
├── .env                   # API keys & DB URL (not committed)
└── travel_plans/          # Auto-saved generated plans
```

## ⚙️ Setup

### 1. Clone and install
```bash
git clone https://github.com/vivekduttsharma2005-hub/triply-mate.git
cd triply-mate
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

### 2. Environment variables
Create a `.env` file in the project root:
```dotenv
GROQ_API_KEY="your_groq_key"
AVIATIONSTACK_API_KEY="your_aviationstack_key"
TAVILY_API_KEY="your_tavily_key"
DATABASE_URL=postgresql://user:password@localhost:5432/langgraph_memory
```

### 3. Run
```bash
streamlit run frontend.py
```
App runs at `https://triply-mate.onrender.com`.

## 🗺️ How It Works

1. User describes a trip (e.g. *"7-day Japan trip under ₹2L"*).
2. The query is sent into a LangGraph state machine.
3. **Flight Agent** searches relevant routes via AviationStack.
4. **Hotel Agent** finds accommodation options.
5. **Itinerary Agent** builds a day-by-day plan.
6. **Final Agent** synthesizes everything into one cohesive travel plan.
7. Results stream live to the UI and are saved as Markdown/JSON.

## ⚠️ Known Limitations

- AviationStack's free tier has limited route coverage — some real-world routes (especially uncommon long-haul ones) may return no results.
- City-to-airport-code mapping is a small manual lookup table (`CITY_TO_IATA` in `flight_tool.py`) — extend as needed.

## 📌 Roadmap

- [ ] Expand city → IATA code coverage
- [ ] Add hotel booking API integration
- [ ] Deploy with managed Postgres (Neon/Supabase)
- [ ] Add authentication for multi-user history

## 📄 License

MIT
