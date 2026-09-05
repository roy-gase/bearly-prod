"""The Bearly financial health score.

Deterministic and fully transparent: six weighted components, each scored from
the user's own numbers against published rules of thumb. The AI is shown this
score and may explain it; it can never alter it.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from app.services.finance.metrics import Overview
from app.services.finance.money import D, ZERO, money

# Weights sum to 100.
WEIGHTS = {
    "savings_rate": 25,
    "emergency_fund": 20,
    "debt_to_income": 20,
    "high_interest_debt": 15,
    "budget_adherence": 10,
    "investment_diversification": 10,
}


def _band(value: Decimal, bands: list[tuple[Decimal, int]]) -> int:
    """bands is ordered best-first as (threshold, points); first match wins."""
    for threshold, points in bands:
        if value >= threshold:
            return points
    return 0


def _score_savings_rate(ov: Overview) -> tuple[int, str]:
    r = ov.savings_rate_pct
    pts = _band(
        r,
        [
            (Decimal(20), 100),
            (Decimal(15), 85),
            (Decimal(10), 70),
            (Decimal(5), 50),
            (Decimal(0), 30),
        ],
    )
    if r < 0:
        pts = 0
        detail = f"You are spending {abs(r):.0f}% more than you earn."
    elif r >= 20:
        detail = f"Saving {r:.0f}% of income — strong."
    elif r >= 10:
        detail = f"Saving {r:.0f}% of income. 20% is the usual target."
    else:
        detail = f"Saving {r:.0f}% of income. Aim for at least 10%."
    return pts, detail


def _score_emergency_fund(ov: Overview) -> tuple[int, str]:
    m = ov.emergency_fund_months
    pts = _band(
        m,
        [
            (Decimal(6), 100),
            (Decimal(3), 80),
            (Decimal(1), 50),
            (Decimal("0.5"), 25),
        ],
    )
    if m >= 6:
        detail = f"{m:.1f} months of essentials covered — fully funded."
    elif m >= 3:
        detail = f"{m:.1f} months covered. Six months is the full target."
    elif m > 0:
        detail = f"Only {m:.1f} months covered. Three months is the first milestone."
    else:
        detail = "No emergency fund yet. This is the highest-leverage fix."
    return pts, detail


def _score_debt_to_income(ov: Overview) -> tuple[int, str]:
    dti = ov.debt_to_income_pct
    if ov.total_debt == 0:
        return 100, "No debt payments — nothing dragging on cash flow."
    if dti <= 10:
        pts, detail = 100, f"Debt payments are {dti:.0f}% of income — very manageable."
    elif dti <= 20:
        pts, detail = 85, f"Debt payments are {dti:.0f}% of income — healthy."
    elif dti <= 36:
        pts, detail = 60, f"Debt payments are {dti:.0f}% of income — near the 36% ceiling."
    elif dti <= 50:
        pts, detail = 30, f"Debt payments are {dti:.0f}% of income — strained."
    else:
        pts, detail = 10, f"Debt payments are {dti:.0f}% of income — unsustainable."
    return pts, detail


def _score_high_interest_debt(ov: Overview) -> tuple[int, str]:
    if ov.total_debt == 0:
        return 100, "No debt."
    hi = ov.high_interest_debt
    if hi == 0:
        return 100, "No high-interest debt — all balances are below 8% APR."
    ratio = money(hi / ov.total_debt * 100) if ov.total_debt else ZERO
    monthly_income = ov.monthly_income
    burden = money(hi / monthly_income) if monthly_income > 0 else Decimal(99)
    if burden <= 1:
        pts = 70
    elif burden <= 3:
        pts = 45
    elif burden <= 6:
        pts = 25
    else:
        pts = 5
    detail = (
        f"${hi:,.0f} sits above 8% APR ({ratio:.0f}% of your debt). "
        "Clearing it beats any expected market return."
    )
    return pts, detail


def _score_budget_adherence(ov: Overview) -> tuple[int, str]:
    if ov.budget_total == 0:
        return 40, "No budget set for this month — set one to score this component."
    util = ov.budget_utilization_pct
    over = ov.over_budget_categories
    if util <= 100 and over == 0:
        pts, detail = 100, f"On plan — {util:.0f}% of budget used, nothing overspent."
    elif util <= 100:
        pts, detail = 75, f"{util:.0f}% of budget used, but {over} category(ies) overspent."
    elif util <= 110:
        pts, detail = 50, f"Slightly over plan at {util:.0f}% of budget."
    else:
        pts, detail = 20, f"Well over plan at {util:.0f}% of budget."
    return pts, detail


def _score_diversification(ov: Overview) -> tuple[int, str]:
    if ov.holding_count == 0:
        if ov.investment_assets > 0:
            return 50, "Investments recorded as a single balance — add holdings for a breakdown."
        return 30, "No investments recorded yet."
    alloc = ov.allocation_by_asset_type or {}
    largest = max((v["pct"] for v in alloc.values()), default=100.0)
    distinct = len(alloc)
    if distinct >= 3 and largest <= 60:
        pts, detail = 100, f"Spread across {distinct} asset types, largest at {largest:.0f}%."
    elif distinct >= 2 and largest <= 80:
        pts, detail = 70, f"{distinct} asset types, largest position class at {largest:.0f}%."
    else:
        pts, detail = 40, f"Concentrated — {largest:.0f}% sits in one asset type."
    return pts, detail


_SCORERS = {
    "savings_rate": ("Savings rate", _score_savings_rate),
    "emergency_fund": ("Emergency fund", _score_emergency_fund),
    "debt_to_income": ("Debt-to-income", _score_debt_to_income),
    "high_interest_debt": ("High-interest debt", _score_high_interest_debt),
    "budget_adherence": ("Budget adherence", _score_budget_adherence),
    "investment_diversification": ("Diversification", _score_diversification),
}

GRADES = [
    (85, "Excellent", "Your finances are in strong shape."),
    (70, "Good", "Solid footing with a couple of things to tighten."),
    (55, "Fair", "The fundamentals need work before you optimise."),
    (35, "Needs work", "There are urgent gaps to close first."),
    (0, "At risk", "Focus on stability before anything else."),
]


def compute_health_score(ov: Overview) -> dict:
    components = []
    weighted_total = Decimal(0)

    for key, weight in WEIGHTS.items():
        label, scorer = _SCORERS[key]
        points, detail = scorer(ov)
        contribution = Decimal(points) * Decimal(weight) / Decimal(100)
        weighted_total += contribution
        components.append(
            {
                "key": key,
                "label": label,
                "score": points,
                "weight": weight,
                "points_earned": float(money(contribution)),
                "points_possible": weight,
                "detail": detail,
            }
        )

    score = int(weighted_total.to_integral_value(rounding="ROUND_HALF_UP"))
    grade, blurb = next((g, b) for threshold, g, b in GRADES if score >= threshold)

    weakest = min(components, key=lambda c: c["score"])
    return {
        "score": score,
        "grade": grade,
        "summary": blurb,
        "components": components,
        "weakest_component": weakest["key"],
        "weakest_label": weakest["label"],
        "methodology": (
            "Six components, each scored 0-100 from your own figures against standard "
            "personal-finance benchmarks, then combined using fixed weights. No AI input."
        ),
    }
