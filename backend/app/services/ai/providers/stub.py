"""Zero-inference provider.

This is the default so Bearly is fully usable with no API credentials and no
per-request cost. It narrates the deterministic engine's own output — which is
where the substance lives anyway — rather than pretending to reason.

It is also the fallback when a real provider fails: the user gets the
calculated guidance instead of an error page.
"""
from __future__ import annotations

from app.models import AgentKind
from app.services.ai.providers.base import ProviderOutput


def _money(value) -> str:
    try:
        return f"${float(value):,.0f}"
    except (TypeError, ValueError):
        return "$0"


def _budget_coach(ctx: dict) -> dict:
    pos = ctx.get("position", {})
    budget = ctx.get("budget", {})
    tops = ctx.get("top_spending_categories", [])
    over = [c for c in tops if c.get("over_by", 0) > 0]

    recs = []
    for i, cat in enumerate(over[:3], start=1):
        recs.append(
            {
                "priority": i,
                "title": f"Bring {cat['name']} back within budget",
                "reason": (
                    f"You budgeted {_money(cat['budgeted'])} for {cat['name']} and have spent "
                    f"{_money(cat['actual'])} — {_money(cat['over_by'])} over."
                ),
                "suggested_amount": round(cat["over_by"], 2),
                "category": cat["name"],
            }
        )

    if not recs:
        discretionary = ctx.get("expense_split", {}).get("discretionary", 0)
        if discretionary > 0:
            recs.append(
                {
                    "priority": 1,
                    "title": "Redirect 10% of discretionary spending to savings",
                    "reason": (
                        f"You spend about {_money(discretionary)}/mo on discretionary items and "
                        "nothing is over budget. Moving a tenth of it raises your savings rate "
                        "without changing your lifestyle much."
                    ),
                    "suggested_amount": round(discretionary * 0.1, 2),
                    "category": "Savings",
                }
            )

    rate = pos.get("savings_rate_pct", 0)
    summary = (
        f"You are bringing in {_money(pos.get('monthly_income'))} and spending "
        f"{_money(pos.get('monthly_expenses'))} a month, which is a savings rate of {rate:.0f}%. "
        + (
            f"{len(over)} budget {'category is' if len(over) == 1 else 'categories are'} over plan."
            if over
            else "Nothing is over budget this month."
        )
    )
    risks = []
    if rate < 10:
        risks.append("A savings rate under 10% leaves little room for surprises.")
    if budget.get("utilization_pct", 0) > 100:
        risks.append("You are spending more than you budgeted overall this month.")

    return {
        "summary": summary,
        "recommendations": recs,
        "risks": risks,
        "next_steps": [
            "Review your three largest categories and set a realistic cap for each.",
            "Log transactions for a full month so these figures come from real spending.",
        ],
    }


def _debt(ctx: dict) -> dict:
    calc = ctx.get("calculated_payoff", {})
    av, sn = calc.get("avalanche", {}), calc.get("snowball", {})
    debts = ctx.get("debts", [])
    saved = calc.get("interest_saved_avalanche_vs_snowball", 0)

    if not debts:
        return {
            "summary": "You have no active debts recorded. Nothing to prioritise here.",
            "recommendations": [],
            "risks": [],
            "next_steps": ["Add any debts you carry so Bearly can model a payoff plan."],
        }

    highest = max(debts, key=lambda d: d.get("apr", 0))
    smallest = min(debts, key=lambda d: d.get("balance", 0))
    summary = (
        f"You carry {_money(ctx.get('position', {}).get('total_debt'))} across {len(debts)} debts "
        f"at a weighted average rate of {ctx.get('weighted_average_apr', 0):.1f}%. "
        f"Paying {_money(av.get('monthly_payment'))} a month, the avalanche method clears "
        f"everything in {av.get('months_to_debt_free', '?')} months for "
        f"{_money(av.get('total_interest'))} in interest; snowball takes "
        f"{sn.get('months_to_debt_free', '?')} months and costs {_money(sn.get('total_interest'))}."
    )
    return {
        "summary": summary,
        "recommendations": [
            {
                "priority": 1,
                "title": f"Target {highest['name']} first (avalanche)",
                "reason": (
                    f"At {highest.get('apr', 0):.1f}% APR it is your most expensive balance. "
                    f"Clearing it first saves {_money(abs(saved))} versus the snowball order."
                ),
                "suggested_amount": ctx.get("extra_available_monthly", 0),
                "category": "Debt",
            },
            {
                "priority": 2,
                "title": f"Or clear {smallest['name']} first (snowball)",
                "reason": (
                    f"At {_money(smallest.get('balance'))} it is your smallest balance, so it "
                    "disappears soonest. It costs more in interest, but a quick win keeps some "
                    "people going."
                ),
                "suggested_amount": 0,
                "category": "Debt",
            },
        ],
        "risks": [
            "These projections assume balances do not grow and every payment is made on time.",
        ],
        "next_steps": [
            "Keep every minimum payment automatic so nothing slips.",
            f"Send any extra {_money(ctx.get('extra_available_monthly'))} to one debt, not spread across all.",
        ],
    }


def _savings(ctx: dict) -> dict:
    ef = ctx.get("emergency_fund", {})
    goals = ctx.get("goals", [])
    surplus = ctx.get("position", {}).get("monthly_cash_flow", 0)
    recs, risks = [], []

    if ef.get("months_covered", 0) < 3:
        shortfall = max(0, ef.get("three_month_target", 0) - ef.get("current", 0))
        recs.append(
            {
                "priority": 1,
                "title": "Fund the emergency fund first",
                "reason": (
                    f"You have {ef.get('months_covered', 0):.1f} months of essentials saved. "
                    f"Reaching three months needs another {_money(shortfall)}."
                ),
                "suggested_amount": round(max(0, surplus) * 0.6, 2),
                "category": "Emergency fund",
            }
        )
        risks.append("Without three months of expenses saved, one setback becomes new debt.")

    for i, g in enumerate(sorted(goals, key=lambda x: x.get("months_remaining") or 999)[:3], start=2):
        if g.get("on_track") is False:
            recs.append(
                {
                    "priority": i,
                    "title": f"Increase contributions to {g['name']}",
                    "reason": (
                        f"{g['name']} needs {_money(g.get('required_monthly'))}/mo to hit its "
                        f"target date; you are putting in {_money(g.get('current_monthly'))}."
                    ),
                    "suggested_amount": g.get("shortfall_monthly", 0),
                    "category": g["name"],
                }
            )

    return {
        "summary": (
            f"You have about {_money(surplus)} a month spare. Your emergency fund covers "
            f"{ef.get('months_covered', 0):.1f} months of essentials, and you are tracking "
            f"{len(goals)} savings goal(s)."
        ),
        "recommendations": recs,
        "risks": risks,
        "next_steps": [
            "Automate a transfer on payday so saving happens before spending.",
            "Keep the emergency fund somewhere separate from day-to-day spending.",
        ],
    }


def _investment(ctx: dict) -> dict:
    readiness = ctx.get("readiness", {})
    if not readiness.get("investing_appropriate", False):
        reason = readiness.get("blocked_reason") or "Your financial basics are not yet in place."
        return {
            "summary": (
                "Investing is not your best next move right now. " + reason
            ),
            "recommendations": [
                {
                    "priority": 1,
                    "title": "Cover the basics before investing",
                    "reason": reason,
                    "suggested_amount": 0,
                    "category": "Foundation",
                }
            ],
            "risks": [
                "Investing before an emergency fund exists often means selling at a loss when "
                "an unexpected bill arrives.",
            ],
            "next_steps": ["Come back to this once the Financial Planner shows investing unblocked."],
        }

    profile = ctx.get("investor_profile", {})
    portfolio = ctx.get("portfolio", {})
    alloc = portfolio.get("allocation_by_asset_type", {})
    largest = max((v.get("pct", 0) for v in alloc.values()), default=0)

    recs = [
        {
            "priority": 1,
            "title": "Favour broad, low-cost diversification",
            "reason": (
                f"With a {profile.get('horizon_years', 10)}-year horizon and "
                f"{profile.get('risk_tolerance', 'moderate')} risk tolerance, broad index funds "
                "spread risk across many companies rather than concentrating it."
            ),
            "suggested_amount": readiness.get("surplus_available_monthly", 0),
            "category": "Allocation",
        }
    ]
    if largest > 60:
        recs.append(
            {
                "priority": 2,
                "title": "Reduce concentration",
                "reason": f"{largest:.0f}% of your portfolio sits in a single asset type.",
                "suggested_amount": 0,
                "category": "Allocation",
            }
        )

    return {
        "summary": (
            f"Your foundations are in place, and about "
            f"{_money(readiness.get('surplus_available_monthly'))} a month is genuinely "
            f"investable. Your portfolio is currently {_money(portfolio.get('total_value'))} "
            f"across {portfolio.get('holding_count', 0)} holdings."
        ),
        "recommendations": recs,
        "risks": [
            "Investments can lose value. Nothing here is a guaranteed return.",
            "This is educational information, not personalised investment advice.",
        ],
        "next_steps": [
            "Decide a fixed monthly amount and automate it.",
            "Review the allocation once a year, not once a week.",
        ],
    }


def _planner(ctx: dict) -> dict:
    waterfall = ctx.get("next_dollar_waterfall", [])
    health = ctx.get("health_score", {})
    blocking = ctx.get("blocking_issue")

    active = [s for s in waterfall if s.get("status") not in ("blocked", "check")]
    recs = [
        {
            "priority": s["rank"],
            "title": s["step"],
            "reason": f"Step {s['rank']} in your plan — status: {s['status'].replace('_', ' ')}.",
            "suggested_amount": s.get("suggested_monthly", 0),
            "category": "Plan",
        }
        for s in active[:5]
    ]

    if blocking == "negative_cash_flow":
        summary = (
            "You are spending more than you earn, so that is the only thing worth working on "
            "right now. Every other goal is being funded by borrowing until this is closed."
        )
    else:
        summary = (
            f"Your financial health score is {health.get('score', 0)} out of 100 "
            f"({health.get('grade', 'Fair')}). The weakest area is "
            f"{health.get('weakest_component', 'your savings rate')}. With "
            f"{_money(ctx.get('monthly_surplus'))} a month spare, the plan below puts it to work "
            "in the order that helps you most."
        )

    return {
        "summary": summary,
        "recommendations": recs,
        "risks": (
            ["Cash flow is negative — this compounds every month it continues."]
            if blocking
            else []
        ),
        "next_steps": [step["step"] for step in waterfall[:3]],
    }


_HANDLERS = {
    AgentKind.BUDGET_COACH.value: _budget_coach,
    AgentKind.DEBT_STRATEGIST.value: _debt,
    AgentKind.SAVINGS_PLANNER.value: _savings,
    AgentKind.INVESTMENT_RESEARCH.value: _investment,
    AgentKind.FINANCIAL_PLANNER.value: _planner,
}


class StubProvider:
    name = "stub"

    def run(self, agent: str, system_prompt: str, context: dict, model: str) -> ProviderOutput:
        handler = _HANDLERS.get(agent)
        if handler is None:
            raise ValueError(f"Unknown agent: {agent}")
        return ProviderOutput(payload=handler(context), model="deterministic")
