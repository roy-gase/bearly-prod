"""Tools the chat agent can call.

Every tool is a thin wrapper over the deterministic finance engine. The model
decides *which* question to ask and how to explain the answer; it never computes
a figure itself. That is the whole point of this module: when the user asks
"what if I paid $600 a month?", the real amortisation runs.

Tool results are aggregates only — no names, no raw transactions, no merchants.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AgentKind, Debt, SavingsGoal, Transaction, TransactionType, User
from app.services.finance import debt as debt_engine
from app.services.finance.health import compute_health_score
from app.services.finance.metrics import build_overview, month_bounds
from app.services.finance.money import D, ZERO, money, total
from app.services.finance.priorities import build_priorities
from app.services.finance.projections import compound_growth, goal_requirement

# --- Tool schemas ----------------------------------------------------------
# Descriptions are deliberately terse: they are resent on every turn, so every
# word costs tokens on every message.

TOOL_SCHEMAS: List[dict] = [
    {
        "name": "get_financial_snapshot",
        "description": "The user's current position: income, expenses, cash flow, savings rate, net worth, emergency fund, debt totals, budget use. Call before giving any advice that depends on their numbers.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "get_priorities",
        "description": "Bearly's next-dollar waterfall and whether investing is appropriate yet. Authoritative ordering — do not reorder it.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "compare_debt_strategies",
        "description": "Run the real amortisation engine: avalanche vs snowball vs minimums-only, given an extra monthly payment. Use for any 'what if I paid X' debt question.",
        "input_schema": {
            "type": "object",
            "properties": {
                "extra_monthly": {
                    "type": "number",
                    "description": "Extra payment per month on top of minimums. 0 to use their current surplus.",
                }
            },
            "required": ["extra_monthly"],
            "additionalProperties": False,
        },
    },
    {
        "name": "simulate_debt_payoff",
        "description": "Simulate one payoff strategy and return months to debt-free, total interest, and the order debts clear in.",
        "input_schema": {
            "type": "object",
            "properties": {
                "strategy": {"type": "string", "enum": ["avalanche", "snowball", "minimum_only"]},
                "extra_monthly": {"type": "number"},
            },
            "required": ["strategy", "extra_monthly"],
            "additionalProperties": False,
        },
    },
    {
        "name": "project_investment_growth",
        "description": "Compound-growth projection at a fixed assumed rate. Never present the result as a prediction.",
        "input_schema": {
            "type": "object",
            "properties": {
                "monthly_contribution": {"type": "number"},
                "annual_return_pct": {"type": "number", "description": "Assumed yearly return, e.g. 7."},
                "years": {"type": "integer"},
                "principal": {"type": "number", "description": "Starting amount. Omit to use their current portfolio value."},
            },
            "required": ["monthly_contribution", "annual_return_pct", "years"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_savings_goals",
        "description": "Their savings goals with progress, required monthly contribution, and whether each is on track.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "get_budget_breakdown",
        "description": "This month's budget by category: planned, actual, remaining, and what is overspent.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "get_spending_trend",
        "description": "Total income and spending per month over recent months, and the biggest spending categories. Aggregates only.",
        "input_schema": {
            "type": "object",
            "properties": {"months": {"type": "integer", "description": "How many months back, 1-12."}},
            "required": ["months"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_health_score",
        "description": "The financial health score with its six components and why each scored as it did.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "run_specialist_agent",
        "description": "Run one of Bearly's specialist analyses for a full structured recommendation. Use when the user wants a deep review of one area rather than a quick answer.",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent": {
                    "type": "string",
                    "enum": [
                        "budget_coach",
                        "debt_strategist",
                        "savings_planner",
                        "investment_research",
                        "financial_planner",
                    ],
                }
            },
            "required": ["agent"],
            "additionalProperties": False,
        },
    },
]

TOOL_NAMES = [t["name"] for t in TOOL_SCHEMAS]

# Human-readable labels for the "what ran" chips in the UI.
TOOL_LABELS = {
    "get_financial_snapshot": "Read your financial snapshot",
    "get_priorities": "Checked your next-dollar plan",
    "compare_debt_strategies": "Compared payoff strategies",
    "simulate_debt_payoff": "Simulated a payoff plan",
    "project_investment_growth": "Ran a growth projection",
    "get_savings_goals": "Reviewed your savings goals",
    "get_budget_breakdown": "Read this month's budget",
    "get_spending_trend": "Analysed your spending trend",
    "get_health_score": "Recalculated your health score",
    "run_specialist_agent": "Ran a specialist analysis",
}


# --- Implementations -------------------------------------------------------


def _snapshot(db: Session, user: User, _: dict) -> dict:
    ov = build_overview(db, user)
    return {
        "monthly_income": float(ov.monthly_income),
        "monthly_expenses": float(ov.monthly_expenses),
        "monthly_surplus": float(ov.monthly_cash_flow),
        "savings_rate_pct": float(ov.savings_rate_pct),
        "net_worth": float(ov.net_worth),
        "total_assets": float(ov.total_assets),
        "total_debt": float(ov.total_debt),
        "high_interest_debt": float(ov.high_interest_debt),
        "weighted_average_apr": float(ov.weighted_avg_apr),
        "monthly_minimum_payments": float(ov.monthly_minimum_payments),
        "debt_to_income_pct": float(ov.debt_to_income_pct),
        "emergency_fund": float(ov.emergency_fund),
        "emergency_fund_months": float(ov.emergency_fund_months),
        "essential_expenses": float(ov.essential_expenses),
        "discretionary_expenses": float(ov.discretionary_expenses),
        "investments_value": float(ov.holdings_value or ov.investment_assets),
        "risk_tolerance": ov.risk_tolerance,
        "investment_horizon_years": ov.investment_horizon_years,
        "data_basis": {"income": ov.income_basis, "expenses": ov.expense_basis},
    }


def _priorities(db: Session, user: User, _: dict) -> dict:
    p = build_priorities(build_overview(db, user))
    return {
        "monthly_surplus": p["monthly_surplus"],
        "investing_appropriate": p["investing_appropriate"],
        "investing_blocked_reason": p["investing_blocked_reason"],
        "blocking_issue": p["blocking_issue"],
        "steps": [
            {
                "rank": s["rank"],
                "title": s["title"],
                "why": s["why"],
                "status": s["status"],
                "suggested_monthly": s["suggested_monthly"],
            }
            for s in p["steps"]
        ],
    }


def _active_debts(db: Session, user: User) -> List[Debt]:
    return list(
        db.scalars(select(Debt).where(Debt.user_id == user.id, Debt.is_active.is_(True))).all()
    )


def _resolve_extra(db: Session, user: User, requested: Any) -> Decimal:
    extra = D(requested or 0)
    if extra <= 0:
        return max(ZERO, build_overview(db, user).monthly_cash_flow)
    return extra


def _compare_debt(db: Session, user: User, args: dict) -> dict:
    debts = _active_debts(db, user)
    if not debts:
        return {"error": "No debts recorded, so there is nothing to compare."}
    extra = _resolve_extra(db, user, args.get("extra_monthly"))
    inputs = [debt_engine.DebtInput.from_model(d) for d in debts]
    result = debt_engine.compare_strategies(inputs, extra)

    def trim(r: dict) -> dict:
        return {
            "months_to_debt_free": r["months_to_debt_free"],
            "total_interest": r["total_interest"],
            "monthly_payment": r["monthly_payment"],
            "payoff_order": [d["name"] for d in r["per_debt"]],
            "payable": r["payable"],
        }

    return {
        "extra_monthly_used": float(money(extra)),
        "avalanche": trim(result["avalanche"]),
        "snowball": trim(result["snowball"]),
        "minimum_only": trim(result["minimum_only"]),
        "interest_saved_avalanche_vs_snowball": result["interest_saved_avalanche_vs_snowball"],
        "interest_saved_vs_minimum_only": result["interest_saved_vs_minimum_only"],
        "months_saved_vs_minimum_only": result["months_saved_vs_minimum_only"],
        "lower_interest_strategy": result["lower_interest_strategy"],
    }


def _simulate_payoff(db: Session, user: User, args: dict) -> dict:
    debts = _active_debts(db, user)
    if not debts:
        return {"error": "No debts recorded."}
    extra = _resolve_extra(db, user, args.get("extra_monthly"))
    strategy = args.get("strategy", "avalanche")
    inputs = [debt_engine.DebtInput.from_model(d) for d in debts]
    r = debt_engine.simulate_payoff(inputs, strategy, extra).to_dict()
    r.pop("balance_timeline", None)  # chart data, not useful to the model
    r["extra_monthly_used"] = float(money(extra))
    return r


def _project_growth(db: Session, user: User, args: dict) -> dict:
    principal = args.get("principal")
    if principal is None:
        principal = float(build_overview(db, user).holdings_value)
    r = compound_growth(
        D(principal),
        D(args.get("monthly_contribution", 0)),
        D(args.get("annual_return_pct", 7)),
        int(args.get("years", 10)),
    )
    r.pop("series", None)  # yearly series is for the chart
    r["note"] = "Fixed-rate projection, not a forecast. Real returns vary and can be negative."
    return r


def _savings_goals(db: Session, user: User, _: dict) -> dict:
    goals = db.scalars(
        select(SavingsGoal).where(SavingsGoal.user_id == user.id, SavingsGoal.is_active.is_(True))
    ).all()
    ov = build_overview(db, user)
    return {
        "monthly_surplus": float(ov.monthly_cash_flow),
        "emergency_fund_months": float(ov.emergency_fund_months),
        "goals": [
            dict(
                name=g.name,
                type=g.goal_type,
                **{
                    k: v
                    for k, v in goal_requirement(
                        g.target_amount, g.current_amount, g.target_date, g.monthly_contribution
                    ).items()
                    if k
                    in (
                        "target_amount",
                        "current_amount",
                        "remaining",
                        "progress_pct",
                        "months_remaining",
                        "required_monthly",
                        "current_monthly",
                        "on_track",
                        "shortfall_monthly",
                    )
                },
            )
            for g in goals
        ],
    }


def _budget(db: Session, user: User, _: dict) -> dict:
    ov = build_overview(db, user)
    return {
        "total_budgeted": float(ov.budget_total),
        "total_spent": float(ov.budget_spent),
        "utilization_pct": float(ov.budget_utilization_pct),
        "categories_over_budget": ov.over_budget_categories,
        "categories": [
            {
                "name": c.name,
                "kind": c.kind,
                "budgeted": float(c.budgeted),
                "actual": float(c.actual),
                "remaining": float(c.remaining),
                "is_over": c.is_over,
            }
            for c in sorted(ov.categories, key=lambda c: c.actual, reverse=True)[:12]
        ],
    }


def _spending_trend(db: Session, user: User, args: dict) -> dict:
    months = max(1, min(12, int(args.get("months", 6))))
    today = date.today()
    series = []
    for offset in range(months - 1, -1, -1):
        year, month = today.year, today.month - offset
        while month <= 0:
            month += 12
            year -= 1
        start, end = month_bounds(year, month)
        rows = db.scalars(
            select(Transaction).where(
                Transaction.user_id == user.id,
                Transaction.occurred_on >= start,
                Transaction.occurred_on <= end,
            )
        ).all()
        income = total(t.amount for t in rows if t.txn_type == TransactionType.INCOME.value)
        expense = total(t.amount for t in rows if t.txn_type == TransactionType.EXPENSE.value)
        series.append(
            {
                "period": "%d-%02d" % (year, month),
                "income": float(income),
                "expenses": float(expense),
                "net": float(money(income - expense)),
            }
        )

    ov = build_overview(db, user)
    return {
        "months": series,
        "top_categories_this_month": [
            {"name": c.name, "spent": float(c.actual), "kind": c.kind}
            for c in sorted(ov.categories, key=lambda c: c.actual, reverse=True)[:6]
        ],
    }


def _health(db: Session, user: User, _: dict) -> dict:
    h = compute_health_score(build_overview(db, user))
    return {
        "score": h["score"],
        "grade": h["grade"],
        "weakest_component": h["weakest_label"],
        "components": [
            {"label": c["label"], "score": c["score"], "weight": c["weight"], "detail": c["detail"]}
            for c in h["components"]
        ],
    }


def _specialist(db: Session, user: User, args: dict) -> dict:
    from app.services.ai import orchestrator

    agent = args.get("agent")
    if agent not in {a.value for a in AgentKind}:
        return {"error": "Unknown specialist."}
    result = orchestrator.run_agent(db, user, agent)
    return {
        "agent": agent,
        "summary": result.response.summary,
        "recommendations": [r.model_dump() for r in result.response.recommendations],
        "risks": result.response.risks,
        "next_steps": result.response.next_steps,
    }


HANDLERS: Dict[str, Callable[[Session, User, dict], dict]] = {
    "get_financial_snapshot": _snapshot,
    "get_priorities": _priorities,
    "compare_debt_strategies": _compare_debt,
    "simulate_debt_payoff": _simulate_payoff,
    "project_investment_growth": _project_growth,
    "get_savings_goals": _savings_goals,
    "get_budget_breakdown": _budget,
    "get_spending_trend": _spending_trend,
    "get_health_score": _health,
    "run_specialist_agent": _specialist,
}


def execute(db: Session, user: User, name: str, args: Optional[dict] = None) -> dict:
    """Run one tool. Errors are returned as data so the model can recover."""
    handler = HANDLERS.get(name)
    if handler is None:
        return {"error": "Unknown tool: %s" % name}
    try:
        return handler(db, user, args or {})
    except Exception as exc:  # noqa: BLE001 - the model gets a usable message, logs get the type
        return {"error": "That calculation failed (%s)." % type(exc).__name__}
