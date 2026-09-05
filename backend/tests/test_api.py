"""End-to-end API tests, including the isolation guarantee between users."""
from datetime import date

from tests.conftest import register

API = "/api/v1"

PROFILE = {
    "monthly_net_income": 6200,
    "other_monthly_income": 300,
    "checking_balance": 3400,
    "savings_balance": 5000,
    "emergency_savings": 4000,
    "investment_balance": 21000,
    "monthly_housing_cost": 1900,
    "monthly_essential_expenses": 1100,
    "monthly_discretionary_expenses": 900,
    "stated_total_debt": 0,
    "stated_debt_interest_rate": 0,
    "stated_minimum_payments": 0,
    "financial_goals": ["Buy a house", "Retire at 60"],
    "investment_horizon_years": 20,
    "risk_tolerance": "moderate",
}


def test_profile_roundtrip_and_onboarding_status(client, auth):
    assert client.get(f"{API}/profile/status", headers=auth).json()["completed"] is False

    r = client.put(f"{API}/profile", json=PROFILE, headers=auth)
    assert r.status_code == 200
    assert float(r.json()["monthly_net_income"]) == 6200

    status = client.get(f"{API}/profile/status", headers=auth).json()
    assert status["completed"] is True


def test_default_categories_are_seeded(client, auth):
    cats = client.get(f"{API}/budgets/categories", headers=auth).json()
    names = {c["name"] for c in cats}
    assert {"Housing", "Groceries", "Restaurants", "Savings", "Travel"} <= names
    assert len(cats) == 15


def test_transaction_crud_filtering_and_search(client, auth):
    cats = client.get(f"{API}/budgets/categories", headers=auth).json()
    groceries = next(c for c in cats if c["name"] == "Groceries")
    dining = next(c for c in cats if c["name"] == "Restaurants")

    acct = client.post(
        f"{API}/accounts",
        json={"name": "Everyday", "account_type": "checking", "current_balance": 3400},
        headers=auth,
    ).json()

    payloads = [
        ("Whole Foods", 142.50, "expense", groceries["id"]),
        ("Trader Joes", 88.20, "expense", groceries["id"]),
        ("Ramen Bar", 34.00, "expense", dining["id"]),
        ("Paycheck", 3100.00, "income", None),
    ]
    for merchant, amount, ttype, cat in payloads:
        r = client.post(
            f"{API}/transactions",
            json={
                "occurred_on": date.today().isoformat(),
                "amount": amount,
                "merchant": merchant,
                "txn_type": ttype,
                "category_id": cat,
                "account_id": acct["id"],
            },
            headers=auth,
        )
        assert r.status_code == 201, r.text

    page = client.get(f"{API}/transactions", headers=auth).json()
    assert page["total"] == 4
    assert page["sum_income"] == 3100.0
    assert page["sum_expense"] == 264.70

    searched = client.get(f"{API}/transactions?q=Joes", headers=auth).json()
    assert searched["total"] == 1

    by_cat = client.get(f"{API}/transactions?category_id={groceries['id']}", headers=auth).json()
    assert by_cat["total"] == 2

    by_type = client.get(f"{API}/transactions?txn_type=income", headers=auth).json()
    assert by_type["total"] == 1

    by_amount = client.get(f"{API}/transactions?min_amount=100", headers=auth).json()
    assert by_amount["total"] == 2

    txn_id = page["items"][0]["id"]
    patched = client.patch(
        f"{API}/transactions/{txn_id}", json={"merchant": "Renamed"}, headers=auth
    )
    assert patched.status_code == 200
    assert patched.json()["merchant"] == "Renamed"

    assert client.delete(f"{API}/transactions/{txn_id}", headers=auth).status_code == 204
    assert client.get(f"{API}/transactions", headers=auth).json()["total"] == 3


def test_transfer_requires_destination(client, auth):
    r = client.post(
        f"{API}/transactions",
        json={
            "occurred_on": date.today().isoformat(),
            "amount": 100,
            "merchant": "Move to savings",
            "txn_type": "transfer",
        },
        headers=auth,
    )
    assert r.status_code == 422


def test_budget_upsert_and_actuals(client, auth):
    cats = client.get(f"{API}/budgets/categories", headers=auth).json()
    groceries = next(c for c in cats if c["name"] == "Groceries")
    housing = next(c for c in cats if c["name"] == "Housing")
    today = date.today()

    client.post(
        f"{API}/transactions",
        json={
            "occurred_on": today.isoformat(),
            "amount": 700,
            "merchant": "Market",
            "txn_type": "expense",
            "category_id": groceries["id"],
        },
        headers=auth,
    )

    r = client.put(
        f"{API}/budgets",
        json={
            "year": today.year,
            "month": today.month,
            "expected_income": 6500,
            "lines": [
                {"category_id": groceries["id"], "budgeted_amount": 600},
                {"category_id": housing["id"], "budgeted_amount": 1900},
            ],
        },
        headers=auth,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total_budgeted"] == 2500.0
    assert body["total_spent"] == 700.0

    line = next(l for l in body["lines"] if l["category_id"] == groceries["id"])
    assert line["budgeted"] == 600.0
    assert line["actual"] == 700.0
    assert line["remaining"] == -100.0
    assert line["is_over"] is True
    assert round(line["used_pct"]) == 117

    # Re-submitting with one line drops the other.
    r2 = client.put(
        f"{API}/budgets",
        json={
            "year": today.year,
            "month": today.month,
            "expected_income": 6500,
            "lines": [{"category_id": groceries["id"], "budgeted_amount": 800}],
        },
        headers=auth,
    )
    assert r2.json()["total_budgeted"] == 800.0


def test_budget_rejects_foreign_category(client, auth):
    other_headers, _ = register(client, email="other@example.com")
    foreign = client.get(f"{API}/budgets/categories", headers=other_headers).json()[0]
    today = date.today()
    r = client.put(
        f"{API}/budgets",
        json={
            "year": today.year,
            "month": today.month,
            "expected_income": 1000,
            "lines": [{"category_id": foreign["id"], "budgeted_amount": 100}],
        },
        headers=auth,
    )
    assert r.status_code == 404


def test_debt_crud_and_payoff_comparison(client, auth):
    for name, balance, apr, minimum in [
        ("Store card", 900, 6.0, 30),
        ("Visa", 6800, 24.99, 170),
        ("Car loan", 14500, 5.9, 330),
    ]:
        r = client.post(
            f"{API}/debts",
            json={
                "name": name,
                "debt_type": "credit_card",
                "current_balance": balance,
                "apr": apr,
                "minimum_payment": minimum,
            },
            headers=auth,
        )
        assert r.status_code == 201

    summary = client.get(f"{API}/debts/summary", headers=auth).json()
    assert summary["total_debt"] == 22200.0
    assert summary["monthly_minimum_payments"] == 530.0
    assert summary["highest_apr_debt"] == "Visa"
    assert summary["smallest_balance_debt"] == "Store card"
    assert 9 < summary["weighted_average_apr"] < 12

    payoff = client.post(f"{API}/debts/payoff", json={"extra_monthly": 300}, headers=auth).json()
    assert payoff["avalanche"]["total_interest"] < payoff["snowball"]["total_interest"]
    assert payoff["lower_interest_strategy"] == "avalanche"
    assert payoff["avalanche"]["months_to_debt_free"] > 0
    assert len(payoff["avalanche"]["balance_timeline"]) > 1

    single = client.get(f"{API}/debts/payoff/snowball?extra_monthly=300", headers=auth).json()
    assert single["strategy"] == "snowball"


def test_savings_goal_progress_and_contribution(client, auth):
    r = client.post(
        f"{API}/savings/goals",
        json={
            "name": "Emergency fund",
            "goal_type": "emergency_fund",
            "target_amount": 12000,
            "current_amount": 3000,
            "monthly_contribution": 500,
        },
        headers=auth,
    )
    assert r.status_code == 201
    goal = r.json()
    assert goal["progress"]["progress_pct"] == 25.0
    assert goal["progress"]["months_at_current_rate"] == 18

    contributed = client.post(
        f"{API}/savings/goals/{goal['id']}/contribute", json={"amount": 1500}, headers=auth
    ).json()
    assert float(contributed["current_amount"]) == 4500.0
    assert contributed["progress"]["progress_pct"] == 37.5

    summary = client.get(f"{API}/savings/summary", headers=auth).json()
    assert summary["total_saved"] == 4500.0
    assert summary["goal_count"] == 1


def test_investment_holdings_and_allocation(client, auth):
    client.put(f"{API}/profile", json=PROFILE, headers=auth)
    for ticker, name, atype, qty, price, sector, risk in [
        ("VTI", "Total Market ETF", "etf", 40, 250, "Broad", "moderate"),
        ("BND", "Total Bond ETF", "bond", 100, 72, "Fixed income", "low"),
        (None, "Cash reserve", "cash", 1, 3000, None, "low"),
    ]:
        r = client.post(
            f"{API}/investments/holdings",
            json={
                "ticker": ticker,
                "name": name,
                "asset_type": atype,
                "quantity": qty,
                "current_price": price,
                "cost_basis": 1000,
                "sector": sector,
                "risk_category": risk,
            },
            headers=auth,
        )
        assert r.status_code == 201, r.text

    holdings = client.get(f"{API}/investments/holdings", headers=auth).json()
    assert len(holdings) == 3
    assert holdings[0]["market_value"] == 10000.0  # sorted by value, VTI first

    alloc = client.get(f"{API}/investments/allocation", headers=auth).json()
    assert alloc["total_value"] == 20200.0
    assert round(alloc["by_asset_type"]["etf"]["pct"]) == 50
    assert alloc["by_risk"]["low"]["value"] == 10200.0
    assert "readiness" in alloc

    projection = client.post(
        f"{API}/investments/projection",
        json={"principal": 10000, "monthly_contribution": 0, "annual_return_pct": 7, "years": 10},
        headers=auth,
    ).json()
    assert 20000 < projection["future_value"] < 20200


def test_dashboard_aggregates_everything(client, auth):
    client.put(f"{API}/profile", json=PROFILE, headers=auth)
    client.post(
        f"{API}/debts",
        json={
            "name": "Visa",
            "debt_type": "credit_card",
            "current_balance": 5000,
            "apr": 22.9,
            "minimum_payment": 150,
        },
        headers=auth,
    )

    d = client.get(f"{API}/dashboard", headers=auth).json()

    # Assets: 3400 + 5000 + 4000 cash, 21000 investments. Liabilities: 5000.
    assert d["net_worth"]["assets"] == 33400.0
    assert d["net_worth"]["liabilities"] == 5000.0
    assert d["net_worth"]["value"] == 28400.0

    # Income 6500, expenses 3900 -> 2600 surplus, 40% savings rate.
    assert d["cash_flow"]["income"] == 6500.0
    assert d["cash_flow"]["expenses"] == 3900.0
    assert d["cash_flow"]["net"] == 2600.0
    assert d["savings_rate"]["value"] == 40.0

    assert d["debt"]["total"] == 5000.0
    assert d["debt"]["high_interest"] == 5000.0
    assert d["emergency_fund"]["current"] == 4000.0

    assert 0 <= d["health"]["score"] <= 100
    assert len(d["health"]["components"]) == 6

    # High-interest debt must block investing in the waterfall.
    assert d["priorities"]["investing_appropriate"] is False
    assert "APR" in d["priorities"]["investing_blocked_reason"]


def test_snapshot_capture_and_history(client, auth):
    client.put(f"{API}/profile", json=PROFILE, headers=auth)
    first = client.post(f"{API}/dashboard/snapshot", headers=auth)
    assert first.status_code == 200
    # Same day again updates rather than duplicating.
    assert client.post(f"{API}/dashboard/snapshot", headers=auth).status_code == 200

    history = client.get(f"{API}/dashboard/snapshots", headers=auth).json()
    assert len(history) == 1
    assert history[0]["net_worth"] == 33400.0

    flow = client.get(f"{API}/dashboard/cash-flow-history?months=3", headers=auth).json()
    assert len(flow) == 3


# --- Isolation -------------------------------------------------------------


def test_users_cannot_read_or_mutate_each_others_data(client):
    alice, _ = register(client, email="alice@example.com")
    bob, _ = register(client, email="bob@example.com")

    debt_id = client.post(
        f"{API}/debts",
        json={"name": "Alice card", "current_balance": 1000, "apr": 20, "minimum_payment": 50},
        headers=alice,
    ).json()["id"]
    goal_id = client.post(
        f"{API}/savings/goals", json={"name": "Alice goal", "target_amount": 5000}, headers=alice
    ).json()["id"]
    txn_id = client.post(
        f"{API}/transactions",
        json={
            "occurred_on": date.today().isoformat(),
            "amount": 50,
            "merchant": "Alice coffee",
            "txn_type": "expense",
        },
        headers=alice,
    ).json()["id"]
    holding_id = client.post(
        f"{API}/investments/holdings",
        json={"name": "Alice ETF", "asset_type": "etf", "quantity": 1, "current_price": 100},
        headers=alice,
    ).json()["id"]
    account_id = client.post(
        f"{API}/accounts", json={"name": "Alice checking", "account_type": "checking"}, headers=alice
    ).json()["id"]

    # Bob's collections never contain Alice's rows.
    assert client.get(f"{API}/debts", headers=bob).json() == []
    assert client.get(f"{API}/savings/goals", headers=bob).json() == []
    assert client.get(f"{API}/transactions", headers=bob).json()["total"] == 0
    assert client.get(f"{API}/investments/holdings", headers=bob).json() == []
    assert client.get(f"{API}/accounts", headers=bob).json() == []

    # Direct access by id is reported as not-found, never as forbidden, so ids
    # cannot be probed for existence.
    for method, path, payload in [
        ("patch", f"{API}/debts/{debt_id}", {"name": "hacked"}),
        ("delete", f"{API}/debts/{debt_id}", None),
        ("patch", f"{API}/savings/goals/{goal_id}", {"name": "hacked"}),
        ("post", f"{API}/savings/goals/{goal_id}/contribute", {"amount": 10}),
        ("patch", f"{API}/transactions/{txn_id}", {"merchant": "hacked"}),
        ("delete", f"{API}/transactions/{txn_id}", None),
        ("patch", f"{API}/investments/holdings/{holding_id}", {"name": "hacked"}),
        ("patch", f"{API}/accounts/{account_id}", {"name": "hacked"}),
    ]:
        fn = getattr(client, method)
        r = fn(path, json=payload, headers=bob) if payload is not None else fn(path, headers=bob)
        assert r.status_code == 404, f"{method} {path} returned {r.status_code}"

    # Alice's data survived every attempt.
    assert client.get(f"{API}/debts", headers=alice).json()[0]["name"] == "Alice card"
    assert client.get(f"{API}/transactions", headers=alice).json()["total"] == 1


def test_cannot_attach_transaction_to_another_users_account(client):
    alice, _ = register(client, email="alice@example.com")
    bob, _ = register(client, email="bob@example.com")
    alice_account = client.post(
        f"{API}/accounts", json={"name": "Alice checking", "account_type": "checking"}, headers=alice
    ).json()["id"]

    r = client.post(
        f"{API}/transactions",
        json={
            "occurred_on": date.today().isoformat(),
            "amount": 10,
            "merchant": "Sneaky",
            "txn_type": "expense",
            "account_id": alice_account,
        },
        headers=bob,
    )
    assert r.status_code == 404


def test_input_validation_rejects_bad_money(client, auth):
    bad = client.post(
        f"{API}/transactions",
        json={
            "occurred_on": date.today().isoformat(),
            "amount": -50,
            "merchant": "Negative",
            "txn_type": "expense",
        },
        headers=auth,
    )
    assert bad.status_code == 422
    # The error body must not echo the submitted values back.
    assert "-50" not in bad.text

    assert (
        client.post(
            f"{API}/debts",
            json={"name": "Bad APR", "current_balance": 100, "apr": 900, "minimum_payment": 10},
            headers=auth,
        ).status_code
        == 422
    )
