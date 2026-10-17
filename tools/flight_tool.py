"""AviationStack lookup. Returns real flight records only; it has NO fare data."""
import os
import re
from typing import Optional

import requests
from dotenv import load_dotenv

from observability import log

load_dotenv()
IATA_RE = re.compile(r"^[A-Za-z]{3}$")


def search_flights(origin_iata: Optional[str], dest_iata: Optional[str]) -> dict:
    """-> {"flights": [...], "note": str}. Never raises, never invents flights."""
    api_key = os.getenv("AVIATIONSTACK_API_KEY")
    if not api_key:
        return {"flights": [], "note": "Flight lookup is not configured (missing AVIATIONSTACK_API_KEY)."}
    if not (origin_iata and dest_iata and IATA_RE.match(origin_iata) and IATA_RE.match(dest_iata)):
        # The old code called the API with no filter here and returned random flights from anywhere.
        return {"flights": [], "note": "Could not determine both airports, so no live flight lookup was done."}

    params = {
        "access_key": api_key, "limit": 5,
        "dep_iata": origin_iata.upper(), "arr_iata": dest_iata.upper(),
    }
    try:
        # AviationStack's free plan is HTTP-only.
        resp = requests.get("http://api.aviationstack.com/v1/flights", params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        # Only the exception TYPE is reported: requests' messages contain the URL, i.e. the access_key.
        log.warning("flight lookup failed: %s", type(e).__name__)
        return {"flights": [], "note": f"Flight lookup failed ({type(e).__name__})."}

    if "error" in data:
        return {"flights": [], "note": f"Flight API error: {data['error'].get('info', 'unknown')}"}

    flights = []
    for f in (data.get("data") or [])[:5]:
        flights.append(
            {
                "airline": (f.get("airline") or {}).get("name") or "Unknown",
                "flight_number": (f.get("flight") or {}).get("iata") or "",
                "status": f.get("flight_status") or "unknown",
                "departure": (f.get("departure") or {}).get("scheduled") or "",
                "arrival": (f.get("arrival") or {}).get("scheduled") or "",
            }
        )
    if not flights:
        return {
            "flights": [],
            "note": f"No live flights found for {origin_iata.upper()}→{dest_iata.upper()} "
            "(the free plan covers few routes, so this does not mean no flights exist).",
        }
    return {"flights": flights, "note": "Airlines/schedules from AviationStack. Fares are NOT provided by this API."}
