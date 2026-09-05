"""Forward-looking projections: compound growth and goal funding."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from app.services.finance.money import D, ZERO, money, safe_div

MONTHS_PER_YEAR = 12


def compound_growth(
    principal: Decimal,
    monthly_contribution: Decimal,
    annual_return_pct: Decimal,
    years: int,
) -> dict:
    """Future value of a lump sum plus a monthly contribution.

    Contributions are applied at the end of each month (ordinary annuity).
    """
    p = D(principal)
    c = D(monthly_contribution)
    r = D(annual_return_pct) / Decimal(100) / Decimal(MONTHS_PER_YEAR)
    n = int(years) * MONTHS_PER_YEAR

    balance = p
    contributed = ZERO
    series: list[dict] = [{"year": 0, "balance": float(money(balance)), "contributed": 0.0}]

    for month in range(1, n + 1):
        balance = balance * (Decimal(1) + r) + c
        contributed += c
        if month % MONTHS_PER_YEAR == 0:
            series.append(
                {
                    "year": month // MONTHS_PER_YEAR,
                    "balance": float(money(balance)),
                    "contributed": float(money(p + contributed)),
                }
            )

    return {
        "future_value": float(money(balance)),
        "total_contributed": float(money(p + contributed)),
        "growth": float(money(balance - p - contributed)),
        "annual_return_pct": float(D(annual_return_pct)),
        "years": years,
        "series": series,
    }


def months_until(target: Optional[date], today: Optional[date] = None) -> Optional[int]:
    if target is None:
        return None
    today = today or date.today()
    months = (target.year - today.year) * 12 + (target.month - today.month)
    return max(0, months)


def goal_requirement(
    target_amount: Decimal,
    current_amount: Decimal,
    target_date: Optional[date],
    monthly_contribution: Decimal = ZERO,
    today: Optional[date] = None,
) -> dict:
    """What a savings goal needs, and whether the current plan gets there."""
    target = D(target_amount)
    current = D(current_amount)
    contribution = D(monthly_contribution)
    remaining = max(ZERO, target - current)
    progress_pct = float(money(safe_div(current, target) * 100)) if target > 0 else 0.0

    months_left = months_until(target_date, today)
    required_monthly = None
    if months_left is not None and months_left > 0 and remaining > 0:
        required_monthly = float(money(remaining / Decimal(months_left)))
    elif months_left == 0 and remaining > 0:
        required_monthly = float(money(remaining))

    months_at_current_rate = None
    projected_completion = None
    if remaining <= 0:
        months_at_current_rate = 0
    elif contribution > 0:
        months_at_current_rate = int((remaining / contribution).to_integral_value(rounding="ROUND_CEILING"))
        today = today or date.today()
        total_months = today.month - 1 + months_at_current_rate
        projected_completion = date(
            today.year + total_months // 12, total_months % 12 + 1, 1
        ).isoformat()

    on_track = None
    if months_left is not None and months_at_current_rate is not None:
        on_track = months_at_current_rate <= months_left
    elif months_left is None and contribution > 0:
        on_track = True

    return {
        "target_amount": float(money(target)),
        "current_amount": float(money(current)),
        "remaining": float(money(remaining)),
        "progress_pct": progress_pct,
        "months_remaining": months_left,
        "required_monthly": required_monthly,
        "current_monthly": float(money(contribution)),
        "months_at_current_rate": months_at_current_rate,
        "projected_completion": projected_completion,
        "on_track": on_track,
        "shortfall_monthly": (
            float(money(D(required_monthly) - contribution))
            if required_monthly is not None and D(required_monthly) > contribution
            else 0.0
        ),
    }


def emergency_fund_plan(
    monthly_essentials: Decimal, current_fund: Decimal, months_target: int = 3
) -> dict:
    essentials = D(monthly_essentials)
    current = D(current_fund)
    target = money(essentials * Decimal(months_target))
    covered = float(money(safe_div(current, essentials))) if essentials > 0 else 0.0
    return {
        "months_target": months_target,
        "target_amount": float(target),
        "current_amount": float(money(current)),
        "shortfall": float(money(max(ZERO, target - current))),
        "months_covered": covered,
        "is_funded": current >= target,
    }
