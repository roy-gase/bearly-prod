"""Structured context builders.

One job: turn the user's database into the smallest set of numbers each agent
actually needs. Raw transaction histories, account numbers, names and email
addresses never leave the backend — agents receive aggregates only.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AgentKind, Debt, InvestmentHolding, SavingsGoal, User
from app.services.finance import debt as debt_engine
from app.services.finance.health import compute_health_score
from app.services.finance.metrics import Overview, build_overview
from app.services.finance.money import D, money
from app.services.finance.priorities import build_priorities
from app.services.finance.projections import goal_requirement


def fingerprint(context: dict) -> str:
    """Stable hash of the context.

    Two calls with materially identical finances produce the same fingerprint,
    which is what makes the recommendation cache safe: if the numbers the agent
    would see have not changed, neither would its answer.
    """
    canonical = json.dumps(context, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# Rates, ratios and durations lose their meaning when rounded to whole numbers:
# a 9.37% APR is not "9%". These keys keep one decimal place; everything else is
# money and is rounded to whole dollars.
_PRECISE_KEY = re.compile(r"(apr|rate|pct|percent|months|years|ratio)", re.IGNORECASE)


def _round_context(value, key: str = ""):
    """Round figures before hashing and sending.

    Money goes to whole dollars: a $3.14 drift in a checking balance is not a
    reason to pay for inference again, and whole dollars are what the advice is
    expressed in anyway. Rates keep a decimal so the agent quotes them correctly.
    """
    if isinstance(value, float):
        return round(value, 1) if _PRECISE_KEY.search(key) else round(value)
    if isinstance(value, dict):
        return {k: _round_context(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [_round_context(v, key) for v in value]
    return value


def _base_position(ov: Overview) -> dict:
    return {
        "monthly_income": float(ov.monthly_income),
        "monthly_expenses": float(ov.monthly_expenses),
        "monthly_cash_flow": float(ov.monthly_cash_flow),
        "savings_rate_pct": float(ov.savings_rate_pct),
        "emergency_fund_months": float(ov.emergency_fund_months),
        "total_debt": float(ov.total_debt),
        "high_interest_debt": float(ov.high_interest_debt),
        "net_worth": float(ov.net_worth),
    }


def build_budget_coach_context(db: Session, user: User, ov: Overview) -> dict:
    top_categories = sorted(ov.categories, key=lambda c: c.actual, reverse=True)[:8]
    return _round_context(
        {
            "position": _base_position(ov),
            "expense_split": {
                "essential": float(ov.essential_expenses),
                "discretionary": float(ov.discretionary_expenses),
                "housing_pct_of_income": float(ov.housing_ratio_pct),
            },
            "budget": {
                "total_budgeted": float(ov.budget_total),
                "total_spent": float(ov.budget_spent),
                "utilization_pct": float(ov.budget_utilization_pct),
                "categories_over_budget": ov.over_budget_categories,
            },
            "top_spending_categories": [
                {
                    "name": c.name,
                    "kind": c.kind,
                    "budgeted": float(c.budgeted),
                    "actual": float(c.actual),
                    "over_by": float(max(c.actual - c.budgeted, D(0))) if c.budgeted else 0.0,
                }
                for c in top_categories
            ],
            "data_basis": {"income": ov.income_basis, "expenses": ov.expense_basis},
        }
    )


def build_debt_context(db: Session, user: User, ov: Overview, extra_payment: float = 0.0) -> dict:
    debts = db.scalars(
        select(Debt).where(Debt.user_id == user.id, Debt.is_active.is_(True))
    ).all()
    inputs = [debt_engine.DebtInput.from_model(d) for d in debts]
    available_extra = D(extra_payment) if extra_payment else max(D(0), ov.monthly_cash_flow)
    comparison = debt_engine.compare_strategies(inputs, available_extra)

    def trim(result: dict) -> dict:
        """Timelines are for charts, not for the model — drop them from context."""
        return {
            "months_to_debt_free": result["months_to_debt_free"],
            "total_interest": result["total_interest"],
            "monthly_payment": result["monthly_payment"],
            "payoff_order": [d["name"] for d in result["per_debt"]][:6],
        }

    return _round_context(
        {
            "position": _base_position(ov),
            "debts": [
                {
                    "name": d.name,
                    "type": d.debt_type,
                    "balance": float(D(d.current_balance)),
                    "apr": float(D(d.apr)),
                    "minimum_payment": float(D(d.minimum_payment)),
                }
                for d in debts
            ],
            "weighted_average_apr": float(ov.weighted_avg_apr),
            "extra_available_monthly": float(money(available_extra)),
            # Precomputed by the backend. The agent explains these; it must not
            # recompute or contradict them.
            "calculated_payoff": {
                "avalanche": trim(comparison["avalanche"]),
                "snowball": trim(comparison["snowball"]),
                "minimum_only": trim(comparison["minimum_only"]),
                "interest_saved_avalanche_vs_snowball": comparison[
                    "interest_saved_avalanche_vs_snowball"
                ],
                "months_saved_vs_minimum_only": comparison["months_saved_vs_minimum_only"],
                "lower_interest_strategy": comparison["lower_interest_strategy"],
            },
        }
    )


def build_savings_context(db: Session, user: User, ov: Overview) -> dict:
    goals = db.scalars(
        select(SavingsGoal).where(SavingsGoal.user_id == user.id, SavingsGoal.is_active.is_(True))
    ).all()
    goal_rows = []
    for g in goals:
        req = goal_requirement(
            g.target_amount, g.current_amount, g.target_date, g.monthly_contribution
        )
        goal_rows.append(
            {
                "name": g.name,
                "type": g.goal_type,
                "target": req["target_amount"],
                "saved": req["current_amount"],
                "progress_pct": req["progress_pct"],
                "months_remaining": req["months_remaining"],
                "required_monthly": req["required_monthly"],
                "current_monthly": req["current_monthly"],
                "on_track": req["on_track"],
                "shortfall_monthly": req["shortfall_monthly"],
            }
        )

    return _round_context(
        {
            "position": _base_position(ov),
            "emergency_fund": {
                "current": float(ov.emergency_fund),
                "months_covered": float(ov.emergency_fund_months),
                "three_month_target": float(ov.emergency_fund_target),
            },
            "monthly_essentials": float(
                ov.essential_expenses if ov.essential_expenses > 0 else ov.monthly_expenses
            ),
            "goals": goal_rows,
            "total_committed_monthly": float(ov.goals_monthly_contribution),
        }
    )


def build_investment_context(db: Session, user: User, ov: Overview) -> dict:
    priorities = build_priorities(ov)
    holdings = db.scalars(
        select(InvestmentHolding).where(InvestmentHolding.user_id == user.id)
    ).all()

    return _round_context(
        {
            "position": _base_position(ov),
            "investor_profile": {
                "risk_tolerance": ov.risk_tolerance,
                "horizon_years": ov.investment_horizon_years,
                "stated_goals": ov.financial_goals[:6],
            },
            "portfolio": {
                "total_value": float(ov.holdings_value),
                "cost_basis": float(ov.holdings_cost_basis),
                "holding_count": ov.holding_count,
                "allocation_by_asset_type": ov.allocation_by_asset_type,
                "allocation_by_risk": ov.allocation_by_risk,
                "largest_positions": [
                    {
                        "name": h.ticker or h.name,
                        "asset_type": h.asset_type,
                        "value": float(h.market_value),
                    }
                    for h in sorted(holdings, key=lambda x: x.market_value, reverse=True)[:6]
                ],
            },
            # The gate. If investing is not appropriate yet, the agent is told so
            # explicitly and must lead with that.
            "readiness": {
                "investing_appropriate": priorities["investing_appropriate"],
                "blocked_reason": priorities["investing_blocked_reason"],
                "surplus_available_monthly": priorities["unallocated"],
            },
        }
    )


def build_planner_context(db: Session, user: User, ov: Overview) -> dict:
    priorities = build_priorities(ov)
    health = compute_health_score(ov)
    return _round_context(
        {
            "position": _base_position(ov),
            "health_score": {
                "score": health["score"],
                "grade": health["grade"],
                "weakest_component": health["weakest_label"],
                "components": [
                    {"label": c["label"], "score": c["score"], "detail": c["detail"]}
                    for c in health["components"]
                ],
            },
            # The waterfall is decided by backend rules. The planner explains and
            # personalises it; it does not reorder it.
            "next_dollar_waterfall": [
                {
                    "rank": s["rank"],
                    "step": s["title"],
                    "status": s["status"],
                    "suggested_monthly": s["suggested_monthly"],
                }
                for s in priorities["steps"]
            ],
            "monthly_surplus": priorities["monthly_surplus"],
            "blocking_issue": priorities["blocking_issue"],
            "investing_appropriate": priorities["investing_appropriate"],
            "investor_profile": {
                "risk_tolerance": ov.risk_tolerance,
                "horizon_years": ov.investment_horizon_years,
                "stated_goals": ov.financial_goals[:6],
            },
        }
    )


BUILDERS = {
    AgentKind.BUDGET_COACH.value: build_budget_coach_context,
    AgentKind.DEBT_STRATEGIST.value: build_debt_context,
    AgentKind.SAVINGS_PLANNER.value: build_savings_context,
    AgentKind.INVESTMENT_RESEARCH.value: build_investment_context,
    AgentKind.FINANCIAL_PLANNER.value: build_planner_context,
}


def build_context(db: Session, user: User, agent: str, ov: Optional[Overview] = None) -> dict:
    ov = ov or build_overview(db, user)
    builder = BUILDERS.get(agent)
    if builder is None:
        raise ValueError(f"Unknown agent: {agent}")
    return builder(db, user, ov)
