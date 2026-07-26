import os
import re
import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("AVIATIONSTACK_API_KEY")

# Minimal city/airport-name -> IATA code lookup.
# Extend this as needed — AviationStack needs IATA codes, not city names.
CITY_TO_IATA = {
    "delhi": "DEL", "new delhi": "DEL",
    "bali": "DPS", "denpasar": "DPS",
    "mumbai": "BOM", "bangalore": "BLR", "bengaluru": "BLR",
    "chennai": "MAA", "kolkata": "CCU", "hyderabad": "HYD",
    "goa": "GOI", "pune": "PNQ",
    "tokyo": "HND", "osaka": "KIX",
    "bangkok": "BKK", "singapore": "SIN",
    "dubai": "DXB", "abu dhabi": "AUH",
    "paris": "CDG", "london": "LHR",
    "rome": "FCO", "new york": "JFK",
    "melbourne": "MEL", "sydney": "SYD",
    "kuala lumpur": "KUL", "ho chi minh city": "SGN", "hanoi": "HAN",
}


def _extract_route(query: str):
    """
    Find an origin and destination city from free-text, regardless of phrasing.

    Instead of relying on brittle "X to Y" / "to Y from X" regex patterns
    (which break on any phrasing we didn't anticipate — e.g. "Mumbai trip
    from Delhi" has no "to" at all), this scans the query for every known
    city name and uses the position of "from"/"to" keywords relative to
    each match to decide which one is the origin and which is the
    destination.
    """
    q = query.lower()

    # Find every known city mentioned in the query, with its position.
    mentions = []  # list of (start_index, city_name)
    for name in CITY_TO_IATA:
        idx = q.find(name)
        if idx != -1:
            mentions.append((idx, name))
    mentions.sort()

    if not mentions:
        return None, None

    # Dedupe overlapping mentions (e.g. "delhi" inside "new delhi")
    deduped = []
    for idx, name in mentions:
        if deduped and idx < deduped[-1][0] + len(deduped[-1][1]):
            if len(name) > len(deduped[-1][1]):
                deduped[-1] = (idx, name)
            continue
        deduped.append((idx, name))
    mentions = deduped

    from_idx = q.find("from")
    to_idx = q.find(" to ")  # spaces avoid matching "to" inside other words

    origin_city = dest_city = None

    if from_idx != -1:
        after_from = [m for m in mentions if m[0] > from_idx]
        if after_from:
            origin_city = after_from[0][1]

    if to_idx != -1:
        after_to = [m for m in mentions if m[0] > to_idx]
        if after_to:
            dest_city = after_to[0][1]

    # Fallback: if we only found one of the two keywords (or neither),
    # use whatever two distinct cities were mentioned, in the order they
    # appear, excluding whichever one we already assigned.
    if origin_city is None or dest_city is None:
        remaining = [name for _, name in mentions if name not in (origin_city, dest_city)]
        if origin_city is None and remaining:
            origin_city = remaining.pop(0)
        if dest_city is None and remaining:
            dest_city = remaining.pop(0)

    def to_iata(city):
        return CITY_TO_IATA.get(city) if city else None

    return to_iata(origin_city), to_iata(dest_city)


def search_flights(query: str):
    if not API_KEY:
        return "Flight search is not configured (missing AVIATIONSTACK_API_KEY)."

    dep_iata, arr_iata = _extract_route(query)

    url = "http://api.aviationstack.com/v1/flights"
    params = {"access_key": API_KEY, "limit": 5}

    if dep_iata:
        params["dep_iata"] = dep_iata
    if arr_iata:
        params["arr_iata"] = arr_iata

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        return f"Flight search failed: {e}"

    if "error" in data:
        return f"Flight API error: {data['error'].get('info', 'unknown error')}"

    flights = []
    for flight in data.get("data", [])[:5]:
        airline = flight.get("airline", {}).get("name", "Unknown")
        departure = flight.get("departure", {}).get("airport", "Unknown")
        arrival = flight.get("arrival", {}).get("airport", "Unknown")
        status = flight.get("flight_status", "Unknown")

        flights.append(
            f"Airline: {airline}\nDeparture: {departure}\nArrival: {arrival}\nStatus: {status}\n"
        )

    if not flights:
        route_desc = f"{dep_iata or '?'} → {arr_iata or '?'}"
        return (
            f"No scheduled flights found for route {route_desc}. "
            f"Note: AviationStack's free tier only covers a limited, often real-time-only "
            f"flight dataset — many routes (especially long-haul like Delhi–Bali) may not "
            f"appear even if they exist in reality."
        )

    return "\n".join(flights)