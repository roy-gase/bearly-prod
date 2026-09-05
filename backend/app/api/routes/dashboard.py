from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession, owned_query
from app.models import FinancialSnapshot, Transaction, TransactionType
from app.services.finance.health import compute_health_score
from app.services.finance.metrics import build_overview, month_bounds
from app.services.finance.money import money, total
from app.services.finance.priorities import build_priorities

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
def dashboard(user: CurrentUser, db: DbSession) -> dict:
    """Every widget on the main dashboard, in one request.

    One round trip rather than eight keeps the first paint fast and means all
    the numbers on screen come from a single consistent read.
    """
    ov = build_overview(db, user)
    health = compute_health_score(ov)
    priorities = build_priorities(ov)

    return {
        "as_of": ov.as_of.isoformat(),
        "has_profile": ov.has_profile,
        "net_worth": {
            "value": float(ov.net_worth),
            "assets": float(ov.total_assets),
            "liabilities": float(ov.total_liabilities),
            "cash": float(ov.cash_assets),
            "investments": float(ov.investment_assets),
            "basis": ov.assets_basis,
        },
        "cash_flow": {
            "income": float(ov.monthly_income),
            "expenses": float(ov.monthly_expenses),
            "net": float(ov.monthly_cash_flow),
            "essential": float(ov.essential_expenses),
            "discretionary": float(ov.discretionary_expenses),
            "income_basis": ov.income_basis,
            "expense_basis": ov.expense_basis,
        },
        "savings_rate": {
            "value": float(ov.savings_rate_pct),
            "target": 20.0,
            "monthly_saved": float(ov.monthly_cash_flow),
        },
        "debt": {
            "total": float(ov.total_debt),
            "minimum_payments": float(ov.monthly_minimum_payments),
            "weighted_apr": float(ov.weighted_avg_apr),
            "high_interest": float(ov.high_interest_debt),
            "count": ov.debt_count,
            "debt_to_income_pct": float(ov.debt_to_income_pct),
        },
        "emergency_fund": {
            "current": float(ov.emergency_fund),
            "months_covered": float(ov.emergency_fund_months),
            "target": float(ov.emergency_fund_target),
            "target_months": 3,
        },
        "budget": {
            "budgeted": float(ov.budget_total),
            "spent": float(ov.budget_spent),
            "remaining": float(money(ov.budget_total - ov.budget_spent)),
            "utilization_pct": float(ov.budget_utilization_pct),
            "over_budget_count": ov.over_budget_categories,
            "top_categories": [c.to_dict() for c in sorted(
                ov.categories, key=lambda c: c.actual, reverse=True
            )[:6]],
        },
        "investments": {
            "value": float(ov.holdings_value or ov.investment_assets),
            "cost_basis": float(ov.holdings_cost_basis),
            "by_asset_type": ov.allocation_by_asset_type,
            "by_risk": ov.allocation_by_risk,
            "holding_count": ov.holding_count,
        },
        "goals": {
            "target": float(ov.goals_target),
            "saved": float(ov.goals_saved),
            "monthly": float(ov.goals_monthly_contribution),
            "count": ov.goal_count,
        },
        "health": health,
        "priorities": priorities,
    }


@router.get("/health-score")
def health_score(user: CurrentUser, db: DbSession) -> dict:
    return compute_health_score(build_overview(db, user))


@router.get("/priorities")
def priorities(user: CurrentUser, db: DbSession) -> dict:
    return build_priorities(build_overview(db, user))


@router.get("/cash-flow-history")
def cash_flow_history(
    user: CurrentUser, db: DbSession, months: int = Query(default=6, ge=1, le=24)
) -> list[dict]:
    """Actual income and spending per month, from recorded transactions."""
    today = date.today()
    out = []
    for offset in range(months - 1, -1, -1):
        year = today.year
        month = today.month - offset
        while month <= 0:
            month += 12
            year -= 1
        start, end = month_bounds(year, month)
        rows = db.scalars(
            owned_query(Transaction, user).where(
                Transaction.occurred_on >= start, Transaction.occurred_on <= end
            )
        ).all()
        income = total(t.amount for t in rows if t.txn_type == TransactionType.INCOME.value)
        expense = total(t.amount for t in rows if t.txn_type == TransactionType.EXPENSE.value)
        out.append(
            {
                "period": f"{year}-{month:02d}",
                "label": start.strftime("%b"),
                "income": float(income),
                "expenses": float(expense),
                "net": float(money(income - expense)),
            }
        )
    return out


@router.post("/snapshot")
def capture_snapshot(user: CurrentUser, db: DbSession) -> dict:
    """Record today's headline metrics so progress can be charted over time.

    One row per day; running it again the same day updates that row.
    """
    ov = build_overview(db, user)
    health = compute_health_score(ov)
    today = date.today()

    snapshot = db.scalar(
        owned_query(FinancialSnapshot, user).where(FinancialSnapshot.captured_on == today)
    )
    if snapshot is None:
        snapshot = FinancialSnapshot(
            user_id=user.id, captured_on=today, created_at=datetime.now(timezone.utc)
        )
        db.add(snapshot)

    snapshot.net_worth = ov.net_worth
    snapshot.total_assets = ov.total_assets
    snapshot.total_liabilities = ov.total_liabilities
    snapshot.monthly_income = ov.monthly_income
    snapshot.monthly_expenses = ov.monthly_expenses
    snapshot.monthly_cash_flow = ov.monthly_cash_flow
    snapshot.savings_rate = ov.savings_rate_pct
    snapshot.emergency_fund_months = ov.emergency_fund_months
    snapshot.debt_to_income = ov.debt_to_income_pct
    snapshot.health_score = health["score"]
    snapshot.detail = {
        "cash": float(ov.cash_assets),
        "investments": float(ov.investment_assets),
        "total_debt": float(ov.total_debt),
        "emergency_fund": float(ov.emergency_fund),
        "grade": health["grade"],
    }
    db.commit()
    db.refresh(snapshot)
    return {"captured_on": snapshot.captured_on.isoformat(), "health_score": snapshot.health_score}


@router.get("/snapshots")
def list_snapshots(
    user: CurrentUser, db: DbSession, days: int = Query(default=365, ge=7, le=1825)
) -> list[dict]:
    cutoff = date.today() - timedelta(days=days)
    rows = db.scalars(
        owned_query(FinancialSnapshot, user)
        .where(FinancialSnapshot.captured_on >= cutoff)
        .order_by(FinancialSnapshot.captured_on)
    ).all()
    return [
        {
            "date": s.captured_on.isoformat(),
            "net_worth": float(s.net_worth),
            "total_assets": float(s.total_assets),
            "total_liabilities": float(s.total_liabilities),
            "total_debt": float(s.detail.get("total_debt", 0)) if s.detail else 0.0,
            "savings_rate": float(s.savings_rate),
            "emergency_fund_months": float(s.emergency_fund_months),
            "health_score": s.health_score,
        }
        for s in rows
    ]
