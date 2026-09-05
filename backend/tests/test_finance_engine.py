"""The deterministic engine is the product's foundation — test the maths directly."""
from datetime import date
from decimal import Decimal

import pytest

from app.services.finance.debt import DebtInput, compare_strategies, simulate_payoff
from app.services.finance.metrics import Overview
from app.services.finance.health import compute_health_score
from app.services.finance.money import money
from app.services.finance.priorities import build_priorities
from app.services.finance.projections import compound_growth, goal_requirement

D = Decimal


def _debts():
    """Deliberately shaped so the two strategies disagree: the smallest balance
    carries the lowest rate, so avalanche and snowball pick different targets."""
    return [
        DebtInput(1, "Store card", D("900"), D("6.0"), D("30")),
        DebtInput(2, "Visa", D("6800"), D("24.99"), D("170")),
        DebtInput(3, "Car loan", D("14500"), D("5.9"), D("330")),
    ]


def test_single_debt_matches_hand_computed_amortisation():
    """$1,000 at 12% APR paying $100/mo: standard amortisation gives 11 months."""
    result = simulate_payoff([DebtInput(1, "Loan", D("1000"), D("12"), D("100"))])
    assert result.months_to_debt_free == 11
    # Interest over 11 months on a falling balance lands near $57.
    assert D("50") < result.total_interest < D("65")
    assert float(result.total_paid) == pytest.approx(1000 + float(result.total_interest), abs=0.01)


def test_zero_interest_debt_is_pure_principal():
    result = simulate_payoff([DebtInput(1, "Family loan", D("1200"), D("0"), D("100"))])
    assert result.months_to_debt_free == 12
    assert result.total_interest == D("0.00")


def test_avalanche_costs_less_interest_than_snowball():
    avalanche = simulate_payoff(_debts(), "avalanche", D("300"))
    snowball = simulate_payoff(_debts(), "snowball", D("300"))
    assert avalanche.total_interest < snowball.total_interest
    # Both clear the same debts, so the finish line is close.
    assert abs(avalanche.months_to_debt_free - snowball.months_to_debt_free) <= 2


def test_avalanche_targets_highest_apr_first():
    result = simulate_payoff(_debts(), "avalanche", D("500"))
    assert result.per_debt[0].name == "Visa"  # 24.99% APR


def test_snowball_targets_smallest_balance_first():
    result = simulate_payoff(_debts(), "snowball", D("500"))
    assert result.per_debt[0].name == "Store card"  # the $900 balance
    big = simulate_payoff(
        [
            DebtInput(1, "Big high rate", D("20000"), D("24"), D("400")),
            DebtInput(2, "Small low rate", D("500"), D("4"), D("25")),
        ],
        "snowball",
        D("200"),
    )
    assert big.per_debt[0].name == "Small low rate"


def test_extra_payment_shortens_payoff():
    without = simulate_payoff(_debts(), "avalanche", D("0"))
    with_extra = simulate_payoff(_debts(), "avalanche", D("400"))
    assert with_extra.months_to_debt_free < without.months_to_debt_free
    assert with_extra.total_interest < without.total_interest


def test_payment_below_interest_is_reported_not_looped_forever():
    """A minimum that cannot cover interest must terminate and say so."""
    result = simulate_payoff([DebtInput(1, "Trap", D("10000"), D("29.99"), D("50"))])
    assert result.payable is False
    assert result.months_to_debt_free is None
    assert "not falling" in result.note or "Not paid off" in result.note


def test_no_debts_is_zero_months():
    result = simulate_payoff([])
    assert result.months_to_debt_free == 0
    assert result.total_interest == D("0.00")


def test_compare_strategies_reports_the_cheaper_one():
    out = compare_strategies(_debts(), D("300"))
    assert out["lower_interest_strategy"] == "avalanche"
    assert out["interest_saved_avalanche_vs_snowball"] > 0
    assert out["months_saved_vs_minimum_only"] > 0


# --- Projections -----------------------------------------------------------


def test_compound_growth_lump_sum_only():
    """$10,000 at 7% for 10 years compounded monthly ≈ $20,097."""
    out = compound_growth(D("10000"), D("0"), D("7"), 10)
    assert 20000 < out["future_value"] < 20200
    assert out["total_contributed"] == 10000.0


def test_compound_growth_contributions_beat_deposits():
    out = compound_growth(D("0"), D("500"), D("7"), 20)
    assert out["total_contributed"] == 120000.0
    assert out["future_value"] > out["total_contributed"]
    assert out["growth"] == pytest.approx(out["future_value"] - out["total_contributed"], abs=1)


def test_zero_return_is_just_the_deposits():
    out = compound_growth(D("1000"), D("100"), D("0"), 5)
    assert out["future_value"] == pytest.approx(1000 + 100 * 60, abs=0.01)


def test_goal_requirement_computes_monthly_need():
    out = goal_requirement(
        D("12000"), D("2000"), date(date.today().year + 1, date.today().month, 1), D("500")
    )
    assert out["remaining"] == 10000.0
    assert out["progress_pct"] == pytest.approx(16.67, abs=0.1)
    assert out["required_monthly"] == pytest.approx(833.33, abs=1)
    assert out["on_track"] is False  # $500/mo cannot cover $833/mo


def test_goal_already_met():
    out = goal_requirement(D("5000"), D("5200"), None, D("100"))
    assert out["remaining"] == 0.0
    assert out["months_at_current_rate"] == 0


# --- Health score ----------------------------------------------------------


def _overview(**kwargs) -> Overview:
    base = dict(
        as_of=date.today(),
        monthly_income=D("6000"),
        monthly_expenses=D("4500"),
        monthly_cash_flow=D("1500"),
        essential_expenses=D("3000"),
        savings_rate_pct=D("25"),
        emergency_fund_months=D("6"),
        debt_to_income_pct=D("8"),
        total_debt=D("0"),
        high_interest_debt=D("0"),
        budget_total=D("4500"),
        budget_spent=D("4200"),
        budget_utilization_pct=D("93"),
        holding_count=4,
        allocation_by_asset_type={
            "etf": {"value": 5000, "pct": 50.0},
            "bond": {"value": 3000, "pct": 30.0},
            "cash": {"value": 2000, "pct": 20.0},
        },
    )
    base.update(kwargs)
    return Overview(**base)


def test_healthy_profile_scores_high():
    out = compute_health_score(_overview())
    assert out["score"] >= 85
    assert out["grade"] == "Excellent"


def test_struggling_profile_scores_low():
    out = compute_health_score(
        _overview(
            monthly_cash_flow=D("-400"),
            savings_rate_pct=D("-7"),
            emergency_fund_months=D("0"),
            debt_to_income_pct=D("48"),
            total_debt=D("32000"),
            high_interest_debt=D("22000"),
            budget_utilization_pct=D("118"),
            over_budget_categories=4,
            holding_count=0,
            allocation_by_asset_type={},
        )
    )
    assert out["score"] < 40
    assert out["grade"] in ("Needs work", "At risk")
    assert out["weakest_component"] in ("savings_rate", "emergency_fund")


def test_score_is_bounded_and_weights_sum_to_100():
    out = compute_health_score(_overview())
    assert 0 <= out["score"] <= 100
    assert sum(c["points_possible"] for c in out["components"]) == 100
    assert len(out["components"]) == 6


# --- Priority waterfall ----------------------------------------------------


def test_negative_cash_flow_blocks_everything_else():
    out = build_priorities(_overview(monthly_cash_flow=D("-500"), savings_rate_pct=D("-9")))
    assert out["blocking_issue"] == "negative_cash_flow"
    assert out["investing_appropriate"] is False
    assert len(out["steps"]) == 1


def test_no_emergency_fund_blocks_investing():
    out = build_priorities(_overview(emergency_fund_months=D("0"), emergency_fund=D("0")))
    assert out["investing_appropriate"] is False
    assert "month" in out["investing_blocked_reason"]


def test_high_interest_debt_blocks_investing():
    out = build_priorities(
        _overview(
            emergency_fund_months=D("4"),
            emergency_fund=D("12000"),
            total_debt=D("9000"),
            high_interest_debt=D("9000"),
            weighted_avg_apr=D("22"),
        )
    )
    assert out["investing_appropriate"] is False
    assert "APR" in out["investing_blocked_reason"]


def test_solid_position_unlocks_investing():
    out = build_priorities(_overview(emergency_fund=D("18000"), emergency_fund_months=D("6")))
    assert out["investing_appropriate"] is True
    invest = [s for s in out["steps"] if s["key"] == "invest"][0]
    assert invest["status"] == "ready"
    assert invest["suggested_monthly"] > 0


def test_waterfall_never_allocates_more_than_the_surplus():
    out = build_priorities(
        _overview(monthly_cash_flow=D("800"), emergency_fund=D("0"), emergency_fund_months=D("0"))
    )
    assert out["allocated"] <= out["monthly_surplus"] + 0.01
