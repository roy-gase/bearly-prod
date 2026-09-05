"""Agent orchestration: caching, invalidation, validation and the investing gate."""
from datetime import date

import pytest

from app.services.ai.context import fingerprint
from tests.conftest import register

API = "/api/v1"

HEALTHY = {
    "monthly_net_income": 7000,
    "other_monthly_income": 0,
    "checking_balance": 4000,
    "savings_balance": 8000,
    "emergency_savings": 15000,
    "investment_balance": 40000,
    "monthly_housing_cost": 1800,
    "monthly_essential_expenses": 1200,
    "monthly_discretionary_expenses": 900,
    "stated_total_debt": 0,
    "stated_debt_interest_rate": 0,
    "stated_minimum_payments": 0,
    "financial_goals": ["Retire early"],
    "investment_horizon_years": 25,
    "risk_tolerance": "moderate",
}

STRUGGLING = {
    **HEALTHY,
    "emergency_savings": 0,
    "savings_balance": 200,
    "investment_balance": 0,
    "monthly_net_income": 3200,
    "monthly_housing_cost": 1600,
    "monthly_essential_expenses": 1100,
    "monthly_discretionary_expenses": 800,
    "stated_total_debt": 14000,
    "stated_debt_interest_rate": 24.5,
    "stated_minimum_payments": 420,
}


def test_agent_catalogue_lists_all_five(client, auth):
    client.put(f"{API}/profile", json=HEALTHY, headers=auth)
    body = client.get(f"{API}/ai/agents", headers=auth).json()
    keys = {a["key"] for a in body["agents"]}
    assert keys == {
        "budget_coach",
        "debt_strategist",
        "savings_planner",
        "investment_research",
        "financial_planner",
    }
    # Nothing has been generated yet: opening the page must not trigger inference.
    assert all(a["has_fresh_result"] is False for a in body["agents"])


def test_agent_requires_profile_before_running(client, auth):
    r = client.post(f"{API}/ai/agents/financial_planner/run", json={}, headers=auth).json()
    assert r["provider"] == "none"
    assert "profile" in r["response"]["summary"].lower()


def test_agent_returns_valid_contract(client, auth):
    client.put(f"{API}/profile", json=HEALTHY, headers=auth)
    r = client.post(f"{API}/ai/agents/financial_planner/run", json={}, headers=auth)
    assert r.status_code == 200
    body = r.json()

    assert set(body["response"].keys()) == {"summary", "recommendations", "risks", "next_steps"}
    assert isinstance(body["response"]["summary"], str) and body["response"]["summary"]
    for rec in body["response"]["recommendations"]:
        assert set(rec.keys()) == {
            "priority",
            "title",
            "reason",
            "suggested_amount",
            "category",
        }
        assert isinstance(rec["suggested_amount"], (int, float))
    # Recommendations arrive sorted by priority.
    priorities = [r["priority"] for r in body["response"]["recommendations"]]
    assert priorities == sorted(priorities)


def test_second_run_is_served_from_cache(client, auth):
    client.put(f"{API}/profile", json=HEALTHY, headers=auth)
    first = client.post(f"{API}/ai/agents/budget_coach/run", json={}, headers=auth).json()
    second = client.post(f"{API}/ai/agents/budget_coach/run", json={}, headers=auth).json()

    assert first["cached"] is False
    assert second["cached"] is True
    assert second["generated_at"] == first["generated_at"]


def test_force_refresh_bypasses_cache(client, auth):
    client.put(f"{API}/profile", json=HEALTHY, headers=auth)
    client.post(f"{API}/ai/agents/budget_coach/run", json={}, headers=auth)
    forced = client.post(
        f"{API}/ai/agents/budget_coach/run", json={"force_refresh": True}, headers=auth
    ).json()
    assert forced["cached"] is False


def test_changing_finances_invalidates_the_cached_answer(client, auth):
    client.put(f"{API}/profile", json=HEALTHY, headers=auth)
    first = client.post(f"{API}/ai/agents/budget_coach/run", json={}, headers=auth).json()
    assert first["cached"] is False
    assert client.post(f"{API}/ai/agents/budget_coach/run", json={}, headers=auth).json()["cached"]

    # A materially different income changes the context fingerprint.
    client.put(f"{API}/profile", json={**HEALTHY, "monthly_net_income": 4000}, headers=auth)
    after = client.post(f"{API}/ai/agents/budget_coach/run", json={}, headers=auth).json()
    assert after["cached"] is False


def test_debt_agent_skipped_when_there_is_no_debt(client, auth):
    client.put(f"{API}/profile", json=HEALTHY, headers=auth)
    r = client.post(f"{API}/ai/agents/debt_strategist/run", json={}, headers=auth).json()
    assert r["provider"] == "none"
    assert "no debt" in r["response"]["summary"].lower()


def test_debt_agent_explains_backend_calculated_payoff(client, auth):
    client.put(f"{API}/profile", json=HEALTHY, headers=auth)
    # Opposed on purpose: the small balance is the cheap debt and the large
    # balance is the expensive one, so the two strategies pick different targets.
    for name, balance, apr, minimum in [
        ("Store card", 1000, 5.0, 30),
        ("Visa", 9000, 25.0, 220),
    ]:
        client.post(
            f"{API}/debts",
            json={
                "name": name,
                "current_balance": balance,
                "apr": apr,
                "minimum_payment": minimum,
            },
            headers=auth,
        )
    r = client.post(
        f"{API}/ai/agents/debt_strategist/run", json={"extra_payment": 300}, headers=auth
    ).json()

    # The payoff figures handed to the agent come from the engine, not the model.
    calc = r["context_sent"]["calculated_payoff"]
    assert calc["avalanche"]["months_to_debt_free"] > 0
    assert calc["avalanche"]["total_interest"] < calc["snowball"]["total_interest"]
    assert calc["lower_interest_strategy"] == "avalanche"
    assert calc["avalanche"]["payoff_order"][0] == "Visa"  # highest APR cleared first
    assert calc["snowball"]["payoff_order"][0] == "Store card"  # smallest balance first
    assert r["response"]["recommendations"]


def test_investment_agent_refuses_when_foundations_are_missing(client, auth):
    client.put(f"{API}/profile", json=STRUGGLING, headers=auth)
    r = client.post(f"{API}/ai/agents/investment_research/run", json={}, headers=auth).json()

    assert r["context_sent"]["readiness"]["investing_appropriate"] is False
    summary = r["response"]["summary"].lower()
    assert "not" in summary and "investing" in summary
    # It must not hand out allocation ideas in this state.
    titles = " ".join(rec["title"].lower() for rec in r["response"]["recommendations"])
    assert "basics" in titles or "foundation" in titles


def test_investment_agent_engages_once_foundations_are_solid(client, auth):
    client.put(f"{API}/profile", json=HEALTHY, headers=auth)
    r = client.post(f"{API}/ai/agents/investment_research/run", json={}, headers=auth).json()
    assert r["context_sent"]["readiness"]["investing_appropriate"] is True
    assert any("divers" in rec["title"].lower() for rec in r["response"]["recommendations"])
    assert any("lose value" in risk.lower() for risk in r["response"]["risks"])


def test_planner_leads_with_the_blocking_issue(client, auth):
    client.put(
        f"{API}/profile",
        json={**HEALTHY, "monthly_net_income": 2000, "monthly_housing_cost": 2200},
        headers=auth,
    )
    r = client.post(f"{API}/ai/agents/financial_planner/run", json={}, headers=auth).json()
    assert r["context_sent"]["blocking_issue"] == "negative_cash_flow"
    assert "more than you earn" in r["response"]["summary"]


def test_context_excludes_identifying_information(client, auth):
    """Only aggregates leave the backend — never names, emails or raw transactions."""
    client.put(f"{API}/profile", json=HEALTHY, headers=auth)
    client.post(
        f"{API}/transactions",
        json={
            "occurred_on": date.today().isoformat(),
            "amount": 42,
            "merchant": "Dr Smith Cardiology",
            "notes": "private medical note",
            "txn_type": "expense",
        },
        headers=auth,
    )
    r = client.post(
        f"{API}/ai/agents/budget_coach/run", json={"force_refresh": True}, headers=auth
    ).json()
    blob = str(r["context_sent"])
    assert "a@example.com" not in blob
    assert "Test User" not in blob
    assert "Dr Smith Cardiology" not in blob
    assert "private medical note" not in blob


def test_latest_endpoint_does_not_trigger_generation(client, auth):
    client.put(f"{API}/profile", json=HEALTHY, headers=auth)
    assert client.get(f"{API}/ai/agents/budget_coach/latest", headers=auth).json() is None
    client.post(f"{API}/ai/agents/budget_coach/run", json={}, headers=auth)
    latest = client.get(f"{API}/ai/agents/budget_coach/latest", headers=auth).json()
    assert latest is not None and latest["cached"] is True


def test_usage_and_history_reporting(client, auth):
    client.put(f"{API}/profile", json=HEALTHY, headers=auth)
    client.post(f"{API}/ai/agents/budget_coach/run", json={}, headers=auth)
    client.post(f"{API}/ai/agents/financial_planner/run", json={}, headers=auth)

    usage = client.get(f"{API}/ai/usage", headers=auth).json()
    assert usage["total_generations"] == 2
    assert usage["billed_generations"] == 0  # stub provider costs nothing

    history = client.get(f"{API}/ai/history", headers=auth).json()
    assert len(history) == 2
    assert {h["agent"] for h in history} == {"budget_coach", "financial_planner"}


def test_unknown_agent_is_rejected(client, auth):
    assert client.post(f"{API}/ai/agents/stock_picker/run", json={}, headers=auth).status_code == 404


def test_agent_results_are_private_to_their_owner(client):
    alice, _ = register(client, email="alice@example.com")
    bob, _ = register(client, email="bob@example.com")
    client.put(f"{API}/profile", json=HEALTHY, headers=alice)
    client.post(f"{API}/ai/agents/budget_coach/run", json={}, headers=alice)

    assert client.get(f"{API}/ai/history", headers=bob).json() == []
    assert client.get(f"{API}/ai/agents/budget_coach/latest", headers=bob).json() is None


def test_fingerprint_is_stable_and_sensitive():
    a = {"income": 5000, "expenses": 3000}
    assert fingerprint(a) == fingerprint({"expenses": 3000, "income": 5000})  # key order
    assert fingerprint(a) != fingerprint({"income": 5001, "expenses": 3000})
