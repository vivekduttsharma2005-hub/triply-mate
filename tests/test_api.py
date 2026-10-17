import json

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver

import api
import main
from conftest import FakeLLM
from schemas import TripRequest


@pytest.fixture
def client(monkeypatch):
    graph = main.build_graph(FakeLLM(), InMemorySaver())
    monkeypatch.setattr(api, "get_graph", lambda: graph)
    monkeypatch.delenv("TRIPLY_API_KEY", raising=False)
    return TestClient(api.app)


def events(resp):
    return [json.loads(l) for l in resp.text.splitlines() if l]


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_plan_streams_nodes_then_done(client):
    r = client.post("/plan", json={"query": "3 day Goa trip from Jaipur under 40000", "thread_id": "a"})
    ev = events(r)
    assert r.status_code == 200 and ev[-1]["type"] == "done"
    assert [e["node"] for e in ev if e["type"] == "node"][0] == "parse_query"
    assert "final_plan" in next(e for e in ev if e.get("node") == "final_agent")["update"]
    assert ev[-1]["metrics"]["seconds"] >= 0


def test_plan_validates_input(client):
    assert client.post("/plan", json={"query": "hi", "thread_id": "a"}).status_code == 422


def test_interrupt_and_resume_over_http(monkeypatch):
    graph = main.build_graph(FakeLLM(trip=TripRequest(destination_city="Goa", days=3)), InMemorySaver())
    monkeypatch.setattr(api, "get_graph", lambda: graph)
    monkeypatch.delenv("TRIPLY_API_KEY", raising=False)
    c = TestClient(api.app)
    ev = events(c.post("/plan", json={"query": "3 day Goa trip please", "thread_id": "b"}))
    assert ev[-1] == {"type": "interrupt", "question": "Which city will you be travelling from?"}
    ev = events(c.post("/resume", json={"answer": "Jaipur", "thread_id": "b"}))
    assert ev[-1]["type"] == "done"


def test_api_key_enforced_when_configured(client, monkeypatch):
    monkeypatch.setenv("TRIPLY_API_KEY", "s3cret")
    body = {"query": "3 day Goa trip from Jaipur", "thread_id": "c"}
    assert client.post("/plan", json=body).status_code == 401
    assert client.post("/plan", json=body, headers={"x-api-key": "s3cret"}).status_code == 200
    assert client.get("/health").status_code == 200   # health stays open for the host's checks


def test_missing_config_is_a_clear_error_event_not_http_500(monkeypatch):
    def broken():
        raise RuntimeError("no GROQ_API_KEY")
    monkeypatch.setattr(api, "get_graph", broken)
    monkeypatch.delenv("TRIPLY_API_KEY", raising=False)
    r = TestClient(api.app).post("/plan", json={"query": "3 day Goa trip from Jaipur", "thread_id": "z"})
    ev = events(r)
    assert r.status_code == 200 and ev[0]["type"] == "error" and "not configured correctly" in ev[0]["message"]
