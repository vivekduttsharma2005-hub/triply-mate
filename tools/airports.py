"""City -> IATA airport code, using the airportsdata package instead of a hand-written table."""
from typing import List, Optional

import airportsdata

AIRPORTS = airportsdata.load("IATA")

# airportsdata matches city names literally, which misses tourist names ("Goa", "Delhi", "Manali")
# and returns tiny same-named airports ("Rome, Oregon"). Popular cases are pinned here.
ALIASES = {
    "goa": "GOI", "delhi": "DEL", "new delhi": "DEL", "manali": "KUU", "shimla": "SLV",
    "ajmer": "KQH", "pushkar": "KQH", "udaipur": "UDR", "jodhpur": "JDH", "jaisalmer": "JSA",
    "varanasi": "VNS", "rishikesh": "DED", "kochi": "COK", "kerala": "COK", "leh": "IXL",
    "srinagar": "SXR", "mumbai": "BOM", "bangalore": "BLR", "bengaluru": "BLR", "kolkata": "CCU",
    "chennai": "MAA", "hyderabad": "HYD", "pune": "PNQ", "jaipur": "JAI",
    "bali": "DPS", "denpasar": "DPS", "tokyo": "HND", "kyoto": "KIX", "osaka": "KIX",
    "paris": "CDG", "london": "LHR", "rome": "FCO", "new york": "JFK", "bangkok": "BKK",
    "pattaya": "BKK", "dubai": "DXB", "singapore": "SIN", "kuala lumpur": "KUL",
}


COUNTRY_CODES = {
    "india": "IN", "japan": "JP", "france": "FR", "italy": "IT", "spain": "ES", "germany": "DE", "thailand": "TH",
    "indonesia": "ID", "singapore": "SG", "malaysia": "MY", "vietnam": "VN", "sri lanka": "LK", "nepal": "NP",
    "maldives": "MV", "bhutan": "BT", "united arab emirates": "AE", "uae": "AE", "united kingdom": "GB", "uk": "GB",
    "england": "GB", "united states": "US", "usa": "US", "united states of america": "US", "australia": "AU",
    "switzerland": "CH", "turkey": "TR", "turkiye": "TR", "greece": "GR", "egypt": "EG", "china": "CN",
    "south korea": "KR", "korea": "KR", "canada": "CA", "netherlands": "NL", "portugal": "PT", "russia": "RU",
    "south africa": "ZA", "new zealand": "NZ", "philippines": "PH", "cambodia": "KH", "austria": "AT",
}


def normalize_country(country: Optional[str]) -> Optional[str]:
    """'India' / 'IN' / 'india' -> 'IN'. Unknown names -> None (= no country filter), never a wrong filter."""
    c = (country or "").strip()
    if not c:
        return None
    if len(c) == 2:
        return c.upper()
    return COUNTRY_CODES.get(c.lower())


def city_to_iata(city: str, country: Optional[str] = None) -> List[str]:
    """All airports whose city matches, best first (country filter, then 'International' in the name)."""
    c = (city or "").strip().lower()
    cands = [(code, a) for code, a in AIRPORTS.items() if a["city"].lower() == c]
    code = normalize_country(country)
    if code:
        cands = [x for x in cands if x[1]["country"].upper() == code]
    cands.sort(key=lambda x: ("international" not in x[1]["name"].lower(), x[0]))
    return [code for code, _ in cands]


def resolve_airport(city: Optional[str], country: Optional[str] = None) -> Optional[str]:
    """One airport code for a city, or None if we can't tell (the caller must handle None)."""
    c = (city or "").strip().lower()
    if not c:
        return None
    if c in ALIASES:
        return ALIASES[c]
    codes = city_to_iata(c, country)
    return codes[0] if codes else None
