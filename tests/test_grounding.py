"""The LLM may not invent hotels or call a guessed price 'real'. This is checked in code, against the search results."""
from conftest import cfg
from main import ground_hotels
from schemas import HotelOption

RESULTS = [
    {"title": "Hotels in Goa from 774", "url": "https://oyo.example/goa",
     "snippet": "Spot On Joeys Place Verem Goa 4.3 rating 774 per night. Townhouse Madgaon 1102 per night."},
    {"title": "Goa guide", "url": "https://guide.example/goa", "snippet": "Best beaches in Goa."},
]


def hotel(name, price, estimate=False, url="https://made-up.example"):
    return HotelOption(name=name, price_per_night_inr=price, is_estimate=estimate, source_url=url)


def test_invented_hotel_is_dropped():
    out = ground_hotels([hotel("Royal Taj Fantasy Palace", 900)], RESULTS)
    assert out == []


def test_real_hotel_with_price_in_source_stays_a_listed_price():
    out = ground_hotels([hotel("Spot On Joeys Place", 774)], RESULTS)
    assert len(out) == 1 and out[0].is_estimate is False


def test_price_not_in_source_is_relabelled_as_estimate():
    """This is exactly what happened: the model said 1,200 for a hotel whose page said 774."""
    out = ground_hotels([hotel("Spot On Joeys Place", 1200)], RESULTS)
    assert len(out) == 1 and out[0].is_estimate is True


def test_source_url_is_forced_to_one_the_search_returned():
    out = ground_hotels([hotel("Spot On Joeys Place", 774, url="https://hallucinated.example")], RESULTS)
    assert out[0].source_url == "https://oyo.example/goa"


def test_price_with_thousands_separator_in_source_is_recognised():
    results = [{"title": "x", "url": "https://u", "snippet": "Hotel Marina Bay is Rs 1,500 per night"}]
    assert ground_hotels([hotel("Hotel Marina Bay", 1500)], results)[0].is_estimate is False


def test_estimates_stay_estimates():
    assert ground_hotels([hotel("Townhouse Madgaon", 5000, estimate=True)], RESULTS)[0].is_estimate is True
