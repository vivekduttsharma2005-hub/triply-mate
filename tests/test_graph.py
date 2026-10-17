from langgraph.types import Command

from conftest import FakeLLM, cfg
from schemas import TripRequest
from service import new_run_input, stream_events


def run(graph, query="3 day Goa trip from Jaipur under 40000", thread="t1"):
    return graph.invoke(new_run_input(query), cfg(thread))


def test_happy_path_within_budget(make_graph):
    out = run(make_graph(FakeLLM()))
    assert out["retries"] == 0 and out["total_cost_inr"] <= 40000
    assert len(out["itinerary"]["days"]) == 3
    assert out["flights"]["options"][0]["is_estimate"] is True
    assert "Over budget" not in out["final_plan"]
    assert "https://example.com/goa" in out["final_plan"]          # sources appended by code


def test_over_budget_retries_twice_then_warns_honestly(make_graph):
    llm = FakeLLM(hotel_prices=(60000, 60000, 60000))               # never gets cheaper
    out = run(make_graph(llm))
    assert out["retries"] == 2                                       # loop is bounded
    assert "final_plan" in out                                       # and the graph still reaches the final agent
    assert "Over budget" in out["final_plan"]


def test_cheaper_hotel_found_on_retry(make_graph):
    llm = FakeLLM(hotel_prices=(60000, 3000))
    out = run(make_graph(llm))
    assert out["retries"] == 1 and out["total_cost_inr"] <= 40000
    assert "Over budget" not in out["final_plan"]


def test_no_budget_means_no_loop(make_graph):
    llm = FakeLLM(trip=TripRequest(origin_city="Jaipur", destination_city="Goa", days=3), hotel_prices=(999999,))
    out = run(make_graph(llm))
    assert out["retries"] == 0 and "Over budget" not in out["final_plan"]


def test_missing_origin_asks_then_resumes(make_graph):
    llm = FakeLLM(trip=TripRequest(destination_city="Goa", destination_country="IN", days=3, budget_inr=40000))
    g = make_graph(llm)
    first = list(stream_events(g, new_run_input("3 day Goa trip under 40000"), "t2"))
    assert first[-1] == {"type": "interrupt", "question": "Which city will you be travelling from?"}
    assert not any(e.get("node") == "flight_agent" for e in first)   # agents did NOT run on a guess
    second = list(stream_events(g, Command(resume="Jaipur"), "t2"))
    assert second[-1]["type"] == "done"
    final = g.get_state(cfg("t2")).values
    assert final["origin"] == "Jaipur" and final["origin_iata"] == "JAI"


def test_unparseable_days_answer_asks_again_then_assumes_3(make_graph):
    llm = FakeLLM(trip=TripRequest(origin_city="Jaipur", destination_city="Goa"))
    g = make_graph(llm)
    ev = list(stream_events(g, new_run_input("trip to Goa from Jaipur"), "t3"))
    assert ev[-1]["question"] == "How many days is the trip?"
    ev = list(stream_events(g, Command(resume="not sure"), "t3"))
    assert "just a number" in ev[-1]["question"]
    list(stream_events(g, Command(resume="dunno"), "t3"))
    final = g.get_state(cfg("t3")).values
    assert final["days"] == 3 and "3 days is assumed" in final["final_plan"]


def test_wrong_day_count_from_llm_is_corrected(make_graph):
    out = run(make_graph(FakeLLM(days_returned=5)))                  # LLM keeps returning 5 days for a 3-day trip
    assert len(out["itinerary"]["days"]) == 3


def test_memory_second_message_sees_previous_trip(make_graph):
    llm = FakeLLM()
    g = make_graph(llm)
    run(g, thread="mem")
    llm.prompts.clear()
    run(g, query="make it cheaper", thread="mem")
    parser_prompt = next(p for name, p in llm.prompts if name == "TripRequest")
    assert "Goa" in parser_prompt and "Jaipur" in parser_prompt


def test_llm_failure_degrades_instead_of_crashing(make_graph):
    class Broken(FakeLLM):
        def with_structured_output(self, schema):
            if schema.__name__ in ("FlightResult", "HotelResult"):
                class R:
                    def invoke(self, m): raise RuntimeError("groq down")
                return R()
            return super().with_structured_output(schema)

    out = run(make_graph(Broken()))
    assert out["flights"]["options"] == [] and "final_plan" in out


def test_parser_failure_is_reported_not_turned_into_a_fake_question(make_graph):
    class BadKey(FakeLLM):
        def with_structured_output(self, schema):
            class R:
                def invoke(self, m): raise RuntimeError("401 Invalid API Key")
            return R()

    events = list(stream_events(make_graph(BadKey()), new_run_input("5 day Goa trip from Jaipur under 40000"), "bad"))
    assert events[-1]["type"] == "error" and "Invalid API Key" in events[-1]["message"]
    assert not any(e["type"] == "interrupt" for e in events)


def _llm_with_itineraries(*itineraries):
    """FakeLLM whose itinerary answers come from the given list (last one repeats)."""
    from schemas import Itinerary

    class L(FakeLLM):
        calls = 0
        def with_structured_output(self, schema):
            if schema is Itinerary:
                outer = self
                class R:
                    def invoke(s, m):
                        i = min(outer.calls, len(itineraries) - 1)
                        outer.calls += 1
                        return itineraries[i]
                return R()
            return super().with_structured_output(schema)
    return L()


def _it(n, activities, cost):
    from schemas import DayPlan, Itinerary
    return Itinerary(days=[DayPlan(day=d, activities=activities, estimated_cost_inr=cost) for d in range(1, n + 1)])


def test_zero_cost_itinerary_is_retried_and_the_better_answer_is_used(make_graph):
    llm = _llm_with_itineraries(_it(3, ["x"], 0), _it(3, ["beach", "fort", "market"], 1500))
    out = run(make_graph(llm))
    assert out["chosen"]["breakdown"]["activities"] == 4500 and out["chosen"]["missing"] == []
    assert "Incomplete" not in out["final_plan"]


def test_itinerary_that_stays_empty_is_flagged_not_called_within_budget(make_graph):
    llm = _llm_with_itineraries(_it(3, ["x"], 0))          # model keeps returning zero costs
    out = run(make_graph(llm))
    assert out["chosen"]["missing"] == ["activity and food costs"]
    assert "Incomplete estimate" in out["final_plan"] and "only a minimum" in out["final_plan"]


def test_missing_hotels_and_flights_are_listed(make_graph):
    class NoOptions(FakeLLM):
        def with_structured_output(self, schema):
            if schema.__name__ in ("FlightResult", "HotelResult"):
                class R:
                    def invoke(s, m): return schema(options=[])
                return R()
            return super().with_structured_output(schema)
    out = run(make_graph(NoOptions()))
    assert set(out["chosen"]["missing"]) == {"flight fares", "hotel prices"}


def _hotel_llm(price, estimate):
    from schemas import HotelOption, HotelResult

    class L(FakeLLM):
        def with_structured_output(self, schema):
            if schema is HotelResult:
                class R:
                    def invoke(s, m): return HotelResult(options=[HotelOption(name="Hotel 0", price_per_night_inr=price, is_estimate=estimate)])
                return R()
            return super().with_structured_output(schema)
    return L()


def test_final_plan_cost_table_is_built_from_the_budget_numbers(make_graph):
    out = run(make_graph(FakeLLM()))
    plan, bd = out["final_plan"], out["chosen"]["breakdown"]
    assert "### Cost summary (estimates)" in plan and f"**₹{out['total_cost_inr']:,}**" in plan
    assert plan.count("IndiGo") == 1                          # flights appear once, not as two fake "legs"
    assert f"₹{bd['flights']:,}" in plan and f"₹{bd['hotel']:,}" in plan


def test_hotel_price_label_in_plan_matches_grounding(make_graph):
    listed = run(make_graph(_hotel_llm(3000, estimate=False)))["final_plan"]       # 3000 is in the search snippet
    guessed = run(make_graph(_hotel_llm(4100, estimate=False)), thread="g2")["final_plan"]   # 4100 is not
    assert "price from listing" in listed and "estimated price" not in listed
    assert "estimated price" in guessed and "price from listing" not in guessed    # no more 'estimated' next to 'not an estimate'


def test_plan_notes_missing_weather_in_code_not_by_the_llm(make_graph):
    plan = run(make_graph(FakeLLM()))["final_plan"]
    assert "No weather forecast is available" in plan
