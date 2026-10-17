import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

import main
from schemas import (DayPlan, FlightOption, FlightResult, HotelOption, HotelResult, Itinerary, TripRequest)


class FakeLLM:
    """Stands in for ChatGroq. `trip` is what the parser 'extracts'; hotel prices depend on retry state."""

    def __init__(self, trip=None, hotel_prices=(3000,), days_returned=None):
        self.trip = trip if trip is not None else TripRequest(
            origin_city="Jaipur", origin_country="IN", destination_city="Goa", destination_country="IN",
            days=3, budget_inr=40000, travelers=1)
        self.hotel_prices = list(hotel_prices)   # price used on call 0, retry 1, retry 2...
        self.days_returned = days_returned
        self.hotel_calls = 0
        self.prompts = []

    def with_structured_output(self, schema):
        outer = self

        class Runner:
            def invoke(self, messages):
                prompt = messages[-1].content
                outer.prompts.append((schema.__name__, prompt))
                if schema is TripRequest:
                    return outer.trip
                if schema is FlightResult:
                    return FlightResult(options=[FlightOption(airline="IndiGo", from_code="X", to_code="Y", price_inr=8000)])
                if schema is HotelResult:
                    i = min(outer.hotel_calls, len(outer.hotel_prices) - 1)
                    outer.hotel_calls += 1
                    return HotelResult(options=[HotelOption(name=f"Hotel {i}", price_per_night_inr=outer.hotel_prices[i])])
                if schema is Itinerary:
                    n = outer.days_returned or outer.trip.days or 3
                    return Itinerary(days=[DayPlan(day=d, activities=["beach"], estimated_cost_inr=1000) for d in range(1, n + 1)])
                raise AssertionError(schema)

        return Runner()

    def invoke(self, messages):
        self.prompts.append(("text", messages[-1].content))
        return AIMessage(content="# Your plan")


@pytest.fixture(autouse=True)
def fake_tools(monkeypatch):
    """No test may touch the network."""
    monkeypatch.setattr(main, "tavily_search", lambda q, max_results=5: {
        "results": [{"title": "Goa guide", "url": "https://example.com/goa", "snippet": "Hotel 0, Hotel 1, Hotel 2 and Hotel 3 are listed from 3000"}], "error": None})
    monkeypatch.setattr(main, "search_flights", lambda o, d: {
        "flights": [{"airline": "IndiGo", "flight_number": "6E1", "status": "scheduled", "departure": "", "arrival": ""}],
        "note": "ok"})
    monkeypatch.setattr(main, "forecast", lambda *a, **k: None)


@pytest.fixture
def make_graph():
    def _make(llm):
        return main.build_graph(llm, InMemorySaver())
    return _make


def cfg(thread="t1"):
    return {"configurable": {"thread_id": thread}}
