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
    """Try to pull an origin and destination city from a free-text query."""
    q = query.lower()
    origin_city = dest_city = None

    # Pattern A: "to Y from X"  (e.g. "7 day plan to mumbai from delhi")
    match = re.search(r"\bto\s+([a-z\s]+?)\s+from\s+([a-z\s]+)", q)
    if match:
        dest_city = match.group(1).strip()
        origin_city = match.group(2).strip()
    else:
        # Pattern B: "from X to Y" or plain "X to Y"
        match = re.search(r"(?:from\s+)?([a-z\s]+?)\s+to\s+([a-z\s]+)", q)
        if match:
            origin_city = match.group(1).strip()
            dest_city = match.group(2).strip()

    def to_iata(city):
        if not city:
            return None
        city = city.strip()
        if city in CITY_TO_IATA:
            return CITY_TO_IATA[city]
        # try matching any known city contained in the phrase
        for name, code in CITY_TO_IATA.items():
            if name in city:
                return code
        return None

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