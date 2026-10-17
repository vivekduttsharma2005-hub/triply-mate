from main import budget_router


def test_retry_when_over_budget():
    assert budget_router({"total_cost_inr": 50000, "budget_inr": 40000, "retries": 0}) == "retry"


def test_done_after_max_retries():
    assert budget_router({"total_cost_inr": 50000, "budget_inr": 40000, "retries": 2}) == "done"


def test_done_when_within_budget():
    assert budget_router({"total_cost_inr": 30000, "budget_inr": 40000, "retries": 0}) == "done"


def test_done_when_no_budget_given():
    assert budget_router({"total_cost_inr": 999999, "budget_inr": None, "retries": 0}) == "done"
