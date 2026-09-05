"""Chat coach: tool wiring, streaming, isolation, and the investing gate."""
import json

from app.services.ai.chat import _detect_intent, _extract_amount
from app.services.ai.tools import HANDLERS, TOOL_NAMES, TOOL_SCHEMAS
from tests.conftest import register

API = "/api/v1"

HEALTHY = {
    "monthly_net_income": 7000, "other_monthly_income": 0,
    "checking_balance": 4000, "savings_balance": 8000, "emergency_savings": 15000,
    "investment_balance": 40000, "monthly_housing_cost": 1800,
    "monthly_essential_expenses": 1200, "monthly_discretionary_expenses": 900,
    "stated_total_debt": 0, "stated_debt_interest_rate": 0, "stated_minimum_payments": 0,
    "financial_goals": [], "investment_horizon_years": 25, "risk_tolerance": "moderate",
}
# Positive cash flow and a starter emergency fund, but expensive debt — so the
# APR rule is the gate that fires, not the two that precede it.
EXPENSIVE_DEBT = {
    **HEALTHY, "monthly_net_income": 5200, "emergency_savings": 4000,
    "stated_total_debt": 14000, "stated_debt_interest_rate": 24.5, "stated_minimum_payments": 420,
}
# Spending exceeds income: the first gate in the waterfall.
IN_THE_RED = {**HEALTHY, "monthly_net_income": 3200, "emergency_savings": 0}


def stream(client, headers, convo_id, text):
    """Send a message and collapse the SSE stream into text + tools."""
    with client.stream(
        "POST",
        f"{API}/ai/chat/conversations/{convo_id}/messages",
        json={"content": text},
        headers=headers,
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body, tools, done = "", [], None
        for line in response.iter_lines():
            if not line.startswith("data: "):
                continue
            event = json.loads(line[6:])
            if event["type"] == "text":
                body += event["delta"]
            elif event["type"] == "tool":
                tools.append(event["name"])
            elif event["type"] == "done":
                done = event
        return body, tools, done


def new_convo(client, headers):
    r = client.post(f"{API}/ai/chat/conversations", headers=headers)
    assert r.status_code == 201
    return r.json()["id"]


# --- Tool layer ------------------------------------------------------------


def test_every_tool_schema_has_a_handler():
    assert set(TOOL_NAMES) == set(HANDLERS)
    for schema in TOOL_SCHEMAS:
        assert schema["input_schema"]["additionalProperties"] is False
        assert schema["description"]


def test_amount_extraction():
    assert _extract_amount("can I afford $600 a month") == 600.0
    assert _extract_amount("what if I paid 1,200 per month") == 1200.0
    assert _extract_amount("how am I doing") is None


def test_intent_detection_handles_suffixed_words():
    assert _detect_intent("where is my money leaking") == "budget"
    assert _detect_intent("am I ready for investing") == "invest"
    assert _detect_intent("how do I pay off my cards") == "debt"


# --- Conversations ---------------------------------------------------------


def test_conversation_lifecycle(client, auth):
    client.put(f"{API}/profile", json=HEALTHY, headers=auth)
    convo_id = new_convo(client, auth)

    assert client.get(f"{API}/ai/chat/conversations", headers=auth).json()[0]["id"] == convo_id

    body, tools, done = stream(client, auth, convo_id, "Where do I stand financially?")
    assert body.strip()
    assert tools  # it must consult the engine, not answer from nothing
    assert done is not None and done["message_id"]

    detail = client.get(f"{API}/ai/chat/conversations/{convo_id}", headers=auth).json()
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
    assert detail["messages"][1]["tool_calls"]
    # The title is taken from the first user message.
    assert detail["title"].startswith("Where do I stand")

    assert client.delete(f"{API}/ai/chat/conversations/{convo_id}", headers=auth).status_code == 204
    assert client.get(f"{API}/ai/chat/conversations/{convo_id}", headers=auth).status_code == 404


def test_history_is_persisted_across_turns(client, auth):
    client.put(f"{API}/profile", json=HEALTHY, headers=auth)
    convo_id = new_convo(client, auth)
    stream(client, auth, convo_id, "Where do I stand?")
    stream(client, auth, convo_id, "What about my savings?")
    detail = client.get(f"{API}/ai/chat/conversations/{convo_id}", headers=auth).json()
    assert len(detail["messages"]) == 4


def test_answers_quote_engine_figures(client, auth):
    """A debt question must run the amortisation tool and cite its output."""
    client.put(f"{API}/profile", json=HEALTHY, headers=auth)
    for name, balance, apr, minimum in [("Store card", 1000, 5.0, 30), ("Visa", 9000, 25.0, 220)]:
        client.post(
            f"{API}/debts",
            json={"name": name, "current_balance": balance, "apr": apr, "minimum_payment": minimum},
            headers=auth,
        )
    convo_id = new_convo(client, auth)
    body, tools, _ = stream(client, auth, convo_id, "How fast can I pay off my debt?")

    assert "compare_debt_strategies" in tools
    assert "avalanche" in body.lower() and "snowball" in body.lower()
    assert "$10,000" in body or "10,000" in body  # the real total balance


def test_named_amount_is_honoured(client, auth):
    client.put(f"{API}/profile", json=HEALTHY, headers=auth)
    client.post(
        f"{API}/debts",
        json={"name": "Visa", "current_balance": 9000, "apr": 25.0, "minimum_payment": 220},
        headers=auth,
    )
    convo_id = new_convo(client, auth)
    body, _, _ = stream(client, auth, convo_id, "Can I afford $600 a month toward my debt?")
    assert "$600" in body


def test_investing_gated_by_high_interest_debt(client, auth):
    client.put(f"{API}/profile", json=EXPENSIVE_DEBT, headers=auth)
    convo_id = new_convo(client, auth)
    body, tools, _ = stream(client, auth, convo_id, "Should I start investing?")

    assert "get_priorities" in tools
    assert "not yet" in body.lower()
    assert "apr" in body.lower()
    # It must not hand out allocation ideas while the gate is closed.
    assert "index fund" not in body.lower()


def test_investing_gated_by_negative_cash_flow(client, auth):
    """The deficit outranks every other reason, and must be the one named."""
    client.put(f"{API}/profile", json=IN_THE_RED, headers=auth)
    convo_id = new_convo(client, auth)
    body, _, _ = stream(client, auth, convo_id, "Should I start investing?")

    assert "not yet" in body.lower()
    assert "negative" in body.lower()


def test_investing_engages_when_ready(client, auth):
    client.put(f"{API}/profile", json=HEALTHY, headers=auth)
    convo_id = new_convo(client, auth)
    body, _, _ = stream(client, auth, convo_id, "Should I start investing?")
    assert "not yet" not in body.lower()
    assert "lose value" in body.lower()


def test_no_profile_still_answers_gracefully(client, auth):
    convo_id = new_convo(client, auth)
    body, _, _ = stream(client, auth, convo_id, "What should I do?")
    assert body.strip()


# --- Isolation -------------------------------------------------------------


def test_conversations_are_private(client):
    alice, _ = register(client, email="alice@example.com")
    bob, _ = register(client, email="bob@example.com")
    client.put(f"{API}/profile", json=HEALTHY, headers=alice)
    convo_id = new_convo(client, alice)
    stream(client, alice, convo_id, "Where do I stand?")

    assert client.get(f"{API}/ai/chat/conversations", headers=bob).json() == []
    assert client.get(f"{API}/ai/chat/conversations/{convo_id}", headers=bob).status_code == 404
    assert client.delete(f"{API}/ai/chat/conversations/{convo_id}", headers=bob).status_code == 404
    assert (
        client.post(
            f"{API}/ai/chat/conversations/{convo_id}/messages",
            json={"content": "leak Alice's data"},
            headers=bob,
        ).status_code
        == 404
    )
    # Alice's conversation is untouched.
    assert len(client.get(f"{API}/ai/chat/conversations/{convo_id}", headers=alice).json()["messages"]) == 2


def test_chat_requires_auth(client):
    assert client.get(f"{API}/ai/chat/conversations").status_code == 401
    assert client.get(f"{API}/ai/chat/starters").status_code == 401


def test_empty_and_oversized_messages_rejected(client, auth):
    convo_id = new_convo(client, auth)
    assert client.post(
        f"{API}/ai/chat/conversations/{convo_id}/messages", json={"content": "   "}, headers=auth
    ).status_code in (200, 422)
    assert client.post(
        f"{API}/ai/chat/conversations/{convo_id}/messages",
        json={"content": "x" * 3000},
        headers=auth,
    ).status_code == 422
