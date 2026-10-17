"""Offline stand-in for Groq's server-side tool-call validation.

Groq checks the model's arguments against the tool's JSON schema BEFORE we ever see them. A field that is not
nullable makes the whole call fail with `tool_use_failed` the moment the model sends null for it. These tests catch that.
"""
import json

import pytest
from jsonschema import Draft202012Validator
from langchain_core.utils.function_calling import convert_to_openai_tool

import schemas
from tools.airports import normalize_country, resolve_airport


def groq_errors(model, args):
    params = convert_to_openai_tool(model)["function"]["parameters"]
    return [f"{'/'.join(map(str, e.path))}: {e.message}" for e in Draft202012Validator(params).iter_errors(args)]


def test_regression_exact_output_that_groq_rejected_for_gpt_oss():
    args = json.loads(
        '{"budget_inr": 40000, "days": 5, "origin_city": "Jaipur", "origin_country": "India", "destination_city": "Goa",'
        ' "destination_country": "India", "travelers": 1, "style": null, "interests": null, "start_date": null}'
    )
    assert groq_errors(schemas.TripRequest, args) == []
    req = schemas.TripRequest(**args)
    assert req.interests == [] and req.destination_city == "Goa"


def test_trip_request_accepts_all_nulls():
    keys = schemas.TripRequest.model_fields.keys()
    assert groq_errors(schemas.TripRequest, {k: None for k in keys}) == []


def test_flight_result_accepts_nulls_in_optional_fields():
    args = {"options": [{"airline": "IndiGo", "from_code": "JAI", "to_code": "GOI", "price_inr": 9000, "is_estimate": None, "basis": None}]}
    assert groq_errors(schemas.FlightResult, args) == []
    opt = schemas.FlightResult(**args).options[0]
    assert opt.is_estimate is True and opt.basis == ""      # unknown source is treated as an estimate, never as a quote


def test_hotel_result_accepts_nulls_in_optional_fields():
    args = {"options": [{"name": "X", "price_per_night_inr": 3000, "area": None, "is_estimate": None, "source_url": None}]}
    assert groq_errors(schemas.HotelResult, args) == []
    opt = schemas.HotelResult(**args).options[0]
    assert opt.is_estimate is True and opt.area == ""


def test_itinerary_schema_is_valid():
    args = {"days": [{"day": 1, "activities": ["beach"], "estimated_cost_inr": 1500}]}
    assert groq_errors(schemas.Itinerary, args) == []


@pytest.mark.parametrize("value,code", [("India", "IN"), ("india", "IN"), ("IN", "IN"), ("in", "IN"), ("UAE", "AE"),
                                         ("Narnia", None), ("", None), (None, None)])
def test_country_normalization(value, code):
    assert normalize_country(value) == code


def test_full_country_name_from_the_model_still_finds_the_airport():
    assert resolve_airport("Chandigarh", "India") == "IXC"
    assert resolve_airport("Hanoi", "Vietnam") == "HAN"


def test_groq_now_rejects_a_day_with_no_activities():
    """Your real run produced days with empty activity lists; the schema must make Groq refuse that."""
    bad = {"days": [{"day": 1, "activities": [], "estimated_cost_inr": 0}]}
    assert any("activities" in e for e in groq_errors(schemas.Itinerary, bad))