"""The next-dollar waterfall.

Computed in Python so the ordering is a property of the product, not of a model's
mood. The Financial Planner agent receives this list and explains it; it does not
decide it.

Order of operations, applied to whatever monthly surplus exists:
  1. Cover essential expenses
  2. Cover minimum debt payments
  3. Build a starter emergency fund (1 month of essentials)
  4. Capture any employer retirement match  (advisory only - not modelled)
  5. Clear high-interest debt (>= 8% APR)
  6. Finish the full emergency fund (3-6 months)
  7. Fund defined savings goals by target date
  8. Invest what remains
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from app.services.finance.metrics import HIGH_INTEREST_APR, Overview
from app.services.finance.money import D, ZERO, money

STARTER_EMERGENCY_MONTHS = Decimal(1)
FULL_EMERGENCY_MONTHS = Decimal(3)


def _essentials(ov: Overview) -> Decimal:
    return ov.essential_expenses if ov.essential_expenses > 0 else ov.monthly_expenses


def build_priorities(ov: Overview) -> dict:
    """Return the ranked next-dollar plan with concrete monthly allocations."""
    essentials = _essentials(ov)
    surplus = max(ZERO, ov.monthly_cash_flow)
    remaining = surplus
    steps: list[dict] = []

    def add(
        key: str,
        title: str,
        why: str,
        amount: Decimal,
        status: str,
        target: Optional[Decimal] = None,
    ) -> None:
        amount = max(ZERO, amount)
        # A step that still has a gap but received nothing is not "in progress" —
        # the surplus ran out above it. Say so rather than showing $0 a month
        # against an unmet goal.
        if amount == ZERO and status == "in_progress":
            status = "queued"
            why = f"{why} There is nothing left to allocate here until the step above is funded."
        steps.append(
            {
                "rank": len(steps) + 1,
                "key": key,
                "title": title,
                "why": why,
                "suggested_monthly": float(money(amount)),
                "status": status,
                "target_amount": float(money(target)) if target is not None else None,
            }
        )

    # --- Blocking conditions come first ---------------------------------
    if ov.monthly_cash_flow < 0:
        add(
            "negative_cash_flow",
            "Close the monthly gap first",
            (
                f"You are spending ${abs(ov.monthly_cash_flow):,.0f} more than you earn each "
                "month. Nothing else works until this is fixed — every other goal is being "
                "funded by borrowing."
            ),
            ZERO,
            "urgent",
        )
        return {
            "steps": steps,
            "monthly_surplus": float(money(ov.monthly_cash_flow)),
            "allocated": 0.0,
            "unallocated": 0.0,
            "blocking_issue": "negative_cash_flow",
            "investing_appropriate": False,
            "investing_blocked_reason": (
                "Monthly cash flow is negative. Investing while running a deficit means "
                "borrowing to invest."
            ),
        }

    if ov.monthly_minimum_payments > 0 and ov.monthly_income > 0:
        covered = ov.monthly_income - ov.monthly_expenses >= ZERO
        if not covered:
            add(
                "minimum_payments",
                "Keep every minimum payment current",
                "Missed payments trigger fees and rate increases that compound quickly.",
                ov.monthly_minimum_payments,
                "urgent",
            )

    # --- 1. Starter emergency fund --------------------------------------
    starter_target = money(essentials * STARTER_EMERGENCY_MONTHS)
    starter_gap = max(ZERO, starter_target - ov.emergency_fund)
    if starter_gap > 0:
        allocation = min(remaining, money(starter_gap / Decimal(3)))
        remaining -= allocation
        add(
            "starter_emergency_fund",
            f"Build a ${starter_target:,.0f} starter emergency fund",
            (
                "One month of essential expenses in cash keeps a surprise bill from turning "
                "into new credit-card debt. This comes before extra debt payments."
            ),
            allocation,
            "in_progress" if ov.emergency_fund > 0 else "not_started",
            starter_target,
        )

    # --- 2. Employer match (advisory) -----------------------------------
    add(
        "employer_match",
        "Capture any employer retirement match",
        (
            "If your employer matches contributions, that is an immediate return no debt "
            "payoff or investment can beat. Bearly does not track your workplace plan — "
            "check whether you are contributing enough to get the full match."
        ),
        ZERO,
        "check",
    )

    # --- 3. High-interest debt ------------------------------------------
    if ov.high_interest_debt > 0:
        allocation = remaining if starter_gap <= 0 else money(remaining * Decimal("0.7"))
        allocation = min(remaining, allocation)
        remaining -= allocation
        add(
            "high_interest_debt",
            f"Attack ${ov.high_interest_debt:,.0f} of high-interest debt",
            (
                f"Your weighted average rate is {ov.weighted_avg_apr:.1f}%. Paying this down "
                "is a guaranteed, tax-free return at that rate — better than the long-run "
                "expected return on a diversified portfolio."
            ),
            allocation,
            "in_progress",
            ov.high_interest_debt,
        )

    # --- 4. Full emergency fund -----------------------------------------
    full_target = money(essentials * FULL_EMERGENCY_MONTHS)
    full_gap = max(ZERO, full_target - ov.emergency_fund)
    if full_gap > 0 and starter_gap <= 0:
        allocation = min(remaining, money(full_gap / Decimal(6)))
        remaining -= allocation
        add(
            "full_emergency_fund",
            f"Grow the emergency fund to ${full_target:,.0f}",
            (
                f"You currently have {ov.emergency_fund_months:.1f} months of essentials "
                "covered. Three months is the standard floor; six if your income is variable."
            ),
            allocation,
            "in_progress",
            full_target,
        )

    # --- 5. Savings goals -----------------------------------------------
    if ov.goal_count > 0 and ov.goals_monthly_contribution > 0:
        allocation = min(remaining, ov.goals_monthly_contribution)
        remaining -= allocation
        add(
            "savings_goals",
            "Fund your savings goals",
            f"You have {ov.goal_count} active goal(s) needing "
            f"${ov.goals_monthly_contribution:,.0f}/mo to stay on schedule.",
            allocation,
            "in_progress",
            ov.goals_target,
        )

    # --- 6. Invest the rest ----------------------------------------------
    blocked_reason = _investing_block(ov)
    if blocked_reason is None:
        add(
            "invest",
            "Invest what is left",
            (
                f"With essentials covered, a funded emergency fund and no expensive debt, "
                f"surplus cash can go to long-term investing over your "
                f"{ov.investment_horizon_years}-year horizon."
            ),
            remaining,
            "ready",
        )
        remaining = ZERO
    else:
        add(
            "invest",
            "Investing comes later",
            blocked_reason,
            ZERO,
            "blocked",
        )

    return {
        "steps": steps,
        "monthly_surplus": float(money(surplus)),
        "allocated": float(money(surplus - remaining)),
        "unallocated": float(money(remaining)),
        "blocking_issue": None,
        "investing_appropriate": blocked_reason is None,
        "investing_blocked_reason": blocked_reason,
    }


def _investing_block(ov: Overview) -> Optional[str]:
    """Why aggressive investing is not the right next move, if it isn't."""
    if ov.monthly_cash_flow < 0:
        return (
            "Your monthly cash flow is negative. Investing now would mean funding it with "
            "debt. Close the gap first."
        )
    if ov.emergency_fund_months < STARTER_EMERGENCY_MONTHS:
        return (
            f"You have {ov.emergency_fund_months:.1f} months of expenses saved. Until at "
            "least one month sits in cash, an unexpected bill would force you to sell "
            "investments at a bad time or borrow at a high rate."
        )
    if ov.high_interest_debt > 0:
        return (
            f"${ov.high_interest_debt:,.0f} of your debt is above {HIGH_INTEREST_APR}% APR. "
            "Paying it off is a guaranteed return at that rate; investing is not."
        )
    return None
