"""Open-Meteo weather (free, no API key). Forecast only exists ~16 days ahead."""
from datetime import date, datetime, timedelta
from typing import Optional

import httpx

from observability import log

MAX_AHEAD_DAYS = 15


def geocode(city: str):
    r = httpx.get(
        "https://geocoding-api.open-meteo.com/v1/search", params={"name": city, "count": 1}, timeout=15
    )
    r.raise_for_status()
    res = r.json().get("results") or []
    return (res[0]["latitude"], res[0]["longitude"]) if res else None


def forecast(city: str, start_date: Optional[str], days: int, today: Optional[date] = None) -> Optional[str]:
    """Text summary of the forecast for the trip dates, or None when no honest forecast is possible."""
    if not start_date or not city:
        return None
    today = today or date.today()
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
    except ValueError:
        return None
    last_ok = today + timedelta(days=MAX_AHEAD_DAYS)
    if start < today or start > last_ok:
        return None  # too far ahead (or in the past): a "forecast" would be made up
    end = min(start + timedelta(days=max(days, 1) - 1), last_ok)
    try:
        loc = geocode(city)
        if not loc:
            return None
        r = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": loc[0], "longitude": loc[1], "timezone": "auto",
                "daily": "temperature_2m_max,precipitation_sum",
                "start_date": start.isoformat(), "end_date": end.isoformat(),
            },
            timeout=15,
        )
        r.raise_for_status()
        d = r.json()["daily"]
    except Exception as e:  # network, bad JSON, missing keys: weather is optional
        log.warning("weather lookup failed: %s", type(e).__name__)
        return None
    return "\n".join(
        f"{day}: max {tmax}°C, rain {rain} mm"
        for day, tmax, rain in zip(d["time"], d["temperature_2m_max"], d["precipitation_sum"])
    )
