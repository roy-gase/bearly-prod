"""Debt payoff simulation.

Month-by-month amortisation, run entirely in Python. The AI explains these
numbers; it never produces them.

Model: interest accrues monthly at apr/12 on the running balance, minimum
payments are made on every debt, and any extra payment is directed at a single
target debt chosen by the strategy. When a debt clears, its minimum payment
rolls into the extra pool (the "snowball" effect) for both strategies.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Iterable, Literal, Optional

from app.models import Debt, PayoffStrategy
from app.services.finance.money import D, ZERO, money, rate, total

MAX_MONTHS = 600  # 50 years; beyond this we report "not payable"


@dataclass
class DebtInput:
    id: Optional[int]
    name: str
    balance: Decimal
    apr: Decimal
    minimum_payment: Decimal
    debt_type: str = "other"

    @classmethod
    def from_model(cls, d: Debt) -> "DebtInput":
        return cls(
            id=d.id,
            name=d.name,
            balance=D(d.current_balance),
            apr=D(d.apr),
            minimum_payment=D(d.minimum_payment),
            debt_type=d.debt_type,
        )


@dataclass
class DebtPayoffDetail:
    debt_id: Optional[int]
    name: str
    months_to_payoff: Optional[int]
    interest_paid: Decimal
    payoff_order: int

    def to_dict(self) -> dict:
        return {
            "debt_id": self.debt_id,
            "name": self.name,
            "months_to_payoff": self.months_to_payoff,
            "interest_paid": float(money(self.interest_paid)),
            "payoff_order": self.payoff_order,
        }


@dataclass
class PayoffResult:
    strategy: str
    months_to_debt_free: Optional[int]
    total_interest: Decimal
    total_paid: Decimal
    monthly_payment: Decimal
    per_debt: list[DebtPayoffDetail] = field(default_factory=list)
    balance_timeline: list[dict] = field(default_factory=list)
    payable: bool = True
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "strategy": self.strategy,
            "months_to_debt_free": self.months_to_debt_free,
            "years_to_debt_free": (
                round(self.months_to_debt_free / 12, 1) if self.months_to_debt_free else None
            ),
            "total_interest": float(money(self.total_interest)),
            "total_paid": float(money(self.total_paid)),
            "monthly_payment": float(money(self.monthly_payment)),
            "payable": self.payable,
            "note": self.note,
            "per_debt": [d.to_dict() for d in self.per_debt],
            "balance_timeline": self.balance_timeline,
        }


def _order_key(strategy: str):
    if strategy == PayoffStrategy.AVALANCHE.value:
        # Highest APR first; larger balance breaks ties.
        return lambda d: (-d["apr"], -d["balance"])
    if strategy == PayoffStrategy.SNOWBALL.value:
        # Smallest balance first; higher APR breaks ties.
        return lambda d: (d["balance"], -d["apr"])
    return lambda d: (d["order"],)


def simulate_payoff(
    debts: Iterable[DebtInput],
    strategy: str = PayoffStrategy.AVALANCHE.value,
    extra_monthly: Decimal = ZERO,
    max_months: int = MAX_MONTHS,
) -> PayoffResult:
    live = [
        {
            "id": d.id,
            "name": d.name,
            "balance": D(d.balance),
            "apr": D(d.apr),
            "minimum": D(d.minimum_payment),
            "interest": ZERO,
            "order": i,
            "cleared_month": None,
        }
        for i, d in enumerate(debts)
        if D(d.balance) > 0
    ]

    extra = D(extra_monthly)
    base_minimums = total(d["minimum"] for d in live)
    result = PayoffResult(
        strategy=strategy,
        months_to_debt_free=None,
        total_interest=ZERO,
        total_paid=ZERO,
        monthly_payment=money(base_minimums + extra),
    )

    if not live:
        result.months_to_debt_free = 0
        result.note = "No active debt."
        return result

    timeline: list[dict] = [
        {"month": 0, "balance": float(money(total(d["balance"] for d in live)))}
    ]
    total_interest = ZERO
    total_paid = ZERO
    payoff_rank = 0
    month = 0

    while month < max_months and any(d["balance"] > 0 for d in live):
        month += 1
        budget = base_minimums + extra

        # 1. Accrue interest.
        for d in live:
            if d["balance"] <= 0:
                continue
            monthly_rate = d["apr"] / Decimal(1200)
            interest = money(d["balance"] * monthly_rate)
            d["balance"] += interest
            d["interest"] += interest
            total_interest += interest

        # 2. Pay minimums on every debt still open.
        for d in live:
            if d["balance"] <= 0:
                continue
            pay = min(d["minimum"], d["balance"], budget)
            if pay <= 0:
                continue
            d["balance"] -= pay
            budget -= pay
            total_paid += pay

        # 3. Direct everything left at the strategy's target debt.
        remaining = [d for d in live if d["balance"] > 0]
        remaining.sort(key=_order_key(strategy))
        for d in remaining:
            if budget <= 0:
                break
            pay = min(budget, d["balance"])
            d["balance"] -= pay
            budget -= pay
            total_paid += pay

        # 4. Record newly cleared debts.
        for d in live:
            if d["balance"] <= Decimal("0.005") and d["cleared_month"] is None:
                d["balance"] = ZERO
                payoff_rank += 1
                d["cleared_month"] = month
                d["rank"] = payoff_rank

        outstanding = total(d["balance"] for d in live)
        if month <= 360:
            timeline.append({"month": month, "balance": float(money(outstanding))})

        # A budget that cannot cover accruing interest never terminates.
        if month > 12 and outstanding >= D(timeline[max(0, month - 12)]["balance"]):
            result.payable = False
            result.note = (
                "At this payment level the balance is not falling — interest is "
                "outpacing payments. Increase the monthly amount."
            )
            break

    if all(d["balance"] <= 0 for d in live):
        result.months_to_debt_free = month
    else:
        result.payable = False
        if not result.note:
            result.note = f"Not paid off within {max_months} months at this payment level."

    result.total_interest = money(total_interest)
    result.total_paid = money(total_paid)
    result.balance_timeline = timeline
    result.per_debt = [
        DebtPayoffDetail(
            debt_id=d["id"],
            name=d["name"],
            months_to_payoff=d["cleared_month"],
            interest_paid=money(d["interest"]),
            payoff_order=d.get("rank", 0),
        )
        for d in sorted(live, key=lambda x: (x["cleared_month"] is None, x["cleared_month"] or 0))
    ]
    return result


def compare_strategies(
    debts: Iterable[DebtInput], extra_monthly: Decimal = ZERO
) -> dict:
    """Avalanche vs snowball vs minimums-only, plus the delta between them."""
    debts = list(debts)
    avalanche = simulate_payoff(debts, PayoffStrategy.AVALANCHE.value, extra_monthly)
    snowball = simulate_payoff(debts, PayoffStrategy.SNOWBALL.value, extra_monthly)
    minimum_only = simulate_payoff(debts, PayoffStrategy.MINIMUM_ONLY.value, ZERO)

    interest_saved_vs_snowball = money(snowball.total_interest - avalanche.total_interest)
    interest_saved_vs_minimum = money(minimum_only.total_interest - avalanche.total_interest)

    months_saved = None
    if minimum_only.months_to_debt_free and avalanche.months_to_debt_free:
        months_saved = minimum_only.months_to_debt_free - avalanche.months_to_debt_free

    if interest_saved_vs_snowball > 0:
        recommendation = "avalanche"
        rationale = (
            f"Avalanche costs ${abs(interest_saved_vs_snowball):,.0f} less in interest "
            "because it clears the highest-rate balance first."
        )
    elif interest_saved_vs_snowball < 0:
        recommendation = "snowball"
        rationale = (
            f"Snowball happens to cost ${abs(interest_saved_vs_snowball):,.0f} less here, "
            "and it clears individual debts sooner."
        )
    else:
        recommendation = "either"
        rationale = (
            "Both strategies cost the same in interest for these balances, so pick "
            "whichever you will actually stick with."
        )

    return {
        "avalanche": avalanche.to_dict(),
        "snowball": snowball.to_dict(),
        "minimum_only": minimum_only.to_dict(),
        "extra_monthly": float(money(extra_monthly)),
        "interest_saved_avalanche_vs_snowball": float(interest_saved_vs_snowball),
        "interest_saved_vs_minimum_only": float(interest_saved_vs_minimum),
        "months_saved_vs_minimum_only": months_saved,
        "lower_interest_strategy": recommendation,
        "rationale": rationale,
    }


def debt_summary(debts: list[Debt]) -> dict:
    active = [d for d in debts if D(d.current_balance) > 0]
    balance = total(d.current_balance for d in active)
    minimums = total(d.minimum_payment for d in active)
    weighted_apr = (
        rate(sum(D(d.current_balance) * D(d.apr) for d in active) / balance) if balance > 0 else ZERO
    )
    return {
        "total_debt": float(balance),
        "monthly_minimum_payments": float(minimums),
        "weighted_average_apr": float(weighted_apr),
        "debt_count": len(active),
        "highest_apr_debt": (
            max(active, key=lambda d: D(d.apr)).name if active else None
        ),
        "smallest_balance_debt": (
            min(active, key=lambda d: D(d.current_balance)).name if active else None
        ),
    }
