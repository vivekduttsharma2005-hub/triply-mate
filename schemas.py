"""Pydantic models: the contract between the LLM agents and the rest of the code."""
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class TripRequest(BaseModel):
    """What the parser node extracts from the user's free-text request."""

    origin_city: Optional[str] = Field(None, description="City the user travels FROM, or null if not stated")
    origin_country: Optional[str] = Field(None, description="ISO 3166-1 alpha-2 country of origin city, e.g. IN")
    destination_city: Optional[str] = Field(
        None, description="Main city to fly to. If the user names a country or region, pick its main tourist city"
    )
    destination_country: Optional[str] = Field(None, description="ISO alpha-2 country of the destination, e.g. JP")
    days: Optional[int] = Field(None, ge=1, le=60, description="Trip length in days, or null if not stated")
    budget_inr: Optional[int] = Field(
        None, ge=0, description="TOTAL trip budget in INR (2 lakh = 200000), or null if not stated"
    )
    travelers: Optional[int] = Field(None, ge=1, le=20, description="Number of travelers, null if not stated")
    style: Optional[str] = Field(None, description="budget | mid-range | luxury, null if not stated")
    start_date: Optional[str] = Field(None, description="Trip start as YYYY-MM-DD if the user gave a date")
    # Must be nullable: models often send null for "nothing stated", and Groq rejects the call otherwise.
    interests: Optional[List[str]] = Field(None, description="Interests the user mentioned, or null")

    @field_validator("interests", mode="before")
    @classmethod
    def _no_null_interests(cls, v):
        return v or []


class FlightOption(BaseModel):
    airline: str
    from_code: str
    to_code: str
    # No free flight API gives fares, so this is ALWAYS an estimate and is labelled as one in the UI.
    price_inr: int = Field(ge=0, description="Estimated ROUND-TRIP economy fare PER PERSON in INR")
    is_estimate: Optional[bool] = True
    basis: Optional[str] = Field(None, description="Where the airline/price came from")

    @field_validator("is_estimate", mode="before")
    @classmethod
    def _estimate_default(cls, v):
        return True if v is None else v   # unknown price source => treat as an estimate, never as a quote

    @field_validator("basis", mode="before")
    @classmethod
    def _basis_default(cls, v):
        return v or ""


class FlightResult(BaseModel):
    options: List[FlightOption]


class HotelOption(BaseModel):
    name: str
    price_per_night_inr: int = Field(ge=0, description="Price per room per night in INR")
    area: Optional[str] = None
    is_estimate: Optional[bool] = True
    source_url: Optional[str] = None

    @field_validator("is_estimate", mode="before")
    @classmethod
    def _estimate_default(cls, v):
        return True if v is None else v

    @field_validator("area", mode="before")
    @classmethod
    def _area_default(cls, v):
        return v or ""


class HotelResult(BaseModel):
    options: List[HotelOption]


class DayPlan(BaseModel):
    day: int
    activities: List[str] = Field(min_length=1, description="3 or more specific things to do that day")
    estimated_cost_inr: int = Field(
        ge=0, description="Realistic NON-ZERO per-PERSON cost in INR for the day: food, local transport and entry fees. NOT flights or hotel."
    )


class Itinerary(BaseModel):
    days: List[DayPlan]
