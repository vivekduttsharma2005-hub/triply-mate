from datetime import date

import pytest
import requests

from tools import flight_tool, tavily_tool, weather_tool
from tools.airports import ALIASES, AIRPORTS, city_to_iata, resolve_airport


def test_jaipur_is_JAI():
    assert "JAI" in city_to_iata("jaipur")


@pytest.mark.parametrize("city,country,code", [("Paris", "FR", "CDG"), ("Rome", "IT", "FCO"), ("Goa", "IN", "GOI"),
                                                ("Delhi", "IN", "DEL"), ("Bali", "ID", "DPS"), ("Chandigarh", "IN", "IXC")])
def test_resolve_known_cities(city, country, code):
    assert resolve_airport(city, country) == code


def test_unknown_city_returns_none_not_a_random_airport():
    assert resolve_airport("Atlantis") is None and resolve_airport("") is None and resolve_airport(None) is None


def test_every_alias_is_a_real_airport():
    assert all(code in AIRPORTS for code in ALIASES.values())


def test_flights_without_both_airports_make_no_api_call(monkeypatch):
    monkeypatch.setenv("AVIATIONSTACK_API_KEY", "k")
    monkeypatch.setattr(requests, "get", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not call API")))
    assert flight_tool.search_flights("DEL", None)["flights"] == []


def test_flight_error_does_not_leak_api_key(monkeypatch):
    monkeypatch.setenv("AVIATIONSTACK_API_KEY", "SECRET123")

    def boom(url, params=None, timeout=None):
        raise requests.ConnectionError(f"failed for {url}?access_key=SECRET123")

    monkeypatch.setattr(requests, "get", boom)
    out = flight_tool.search_flights("DEL", "GOI")
    assert out["flights"] == [] and "SECRET123" not in out["note"]


def test_flight_parsing(monkeypatch):
    monkeypatch.setenv("AVIATIONSTACK_API_KEY", "k")

    class R:
        def raise_for_status(self): pass
        def json(self): return {"data": [{"airline": {"name": "IndiGo"}, "flight": {"iata": "6E123"}, "flight_status": "scheduled",
                                          "departure": None, "arrival": {"scheduled": "t"}}]}

    monkeypatch.setattr(requests, "get", lambda *a, **k: R())
    f = flight_tool.search_flights("DEL", "GOI")["flights"][0]
    assert f["airline"] == "IndiGo" and f["flight_number"] == "6E123" and f["departure"] == ""


def test_tavily_without_key_degrades(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    out = tavily_tool.tavily_search("x")
    assert out["results"] == [] and out["error"]


def test_tavily_failure_is_reported_not_raised(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "k")

    class Boom:
        def search(self, **kw): raise RuntimeError("down")

    monkeypatch.setattr(tavily_tool, "_get_client", lambda: Boom())
    assert "RuntimeError" in tavily_tool.tavily_search("x")["error"]


def test_weather_refuses_dates_beyond_forecast_range():
    today = date(2026, 10, 16)
    assert weather_tool.forecast("Goa", "2027-03-01", 5, today=today) is None   # too far ahead
    assert weather_tool.forecast("Goa", "2026-10-01", 5, today=today) is None   # in the past
    assert weather_tool.forecast("Goa", None, 5, today=today) is None
    assert weather_tool.forecast("Goa", "not-a-date", 5, today=today) is None


def test_weather_summary(monkeypatch):
    monkeypatch.setattr(weather_tool, "geocode", lambda c: (1.0, 2.0))

    class R:
        def raise_for_status(self): pass
        def json(self): return {"daily": {"time": ["2026-10-20"], "temperature_2m_max": [31], "precipitation_sum": [4.2]}}

    monkeypatch.setattr(weather_tool.httpx, "get", lambda *a, **k: R())
    assert "2026-10-20: max 31°C, rain 4.2 mm" in weather_tool.forecast("Goa", "2026-10-20", 1, today=date(2026, 10, 16))
