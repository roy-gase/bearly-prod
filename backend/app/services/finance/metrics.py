"""Core financial metrics, computed in Python from the user's own records.

Precedence rule used throughout: real records win over the onboarding profile.
If a user has entered debts, those debts define total liabilities; if they have
not, the profile's stated figure is used. Every metric reports which basis it
used via `*_basis` so the UI and the AI can explain where a number came from.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Account,
    AccountType,
    BudgetCategory,
    BudgetLine,
    CategoryKind,
    Debt,
    FinancialProfile,
    GoalType,
    InvestmentHolding,
    MonthlyBudget,
    SavingsGoal,
    Transaction,
    TransactionType,
    User,
)
from app.services.finance.money import D, ZERO, money, pct, rate, safe_div, total

Basis = Literal["transactions", "profile", "records", "none"]

TRAILING_MONTHS = 3
MIN_EXPENSE_TXNS_FOR_TRAILING = 3


def month_bounds(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    end = date(year + (month == 12), (month % 12) + 1, 1) - timedelta(days=1)
    return start, end


def months_between(start: date, end: date) -> int:
    return max(0, (end.year - start.year) * 12 + (end.month - start.month))


@dataclass
class CategorySpend:
    category_id: Optional[int]
    name: str
    kind: str
    budgeted: Decimal
    actual: Decimal

    @property
    def remaining(self) -> Decimal:
        return money(self.budgeted - self.actual)

    @property
    def used_pct(self) -> Decimal:
        return pct(self.actual, self.budgeted) if self.budgeted > 0 else ZERO

    @property
    def is_over(self) -> bool:
        return self.budgeted > 0 and self.actual > self.budgeted

    def to_dict(self) -> dict:
        return {
            "category_id": self.category_id,
            "name": self.name,
            "kind": self.kind,
            "budgeted": float(self.budgeted),
            "actual": float(self.actual),
            "remaining": float(self.remaining),
            "used_pct": float(self.used_pct),
            "is_over": self.is_over,
        }


@dataclass
class Overview:
    """Everything the dashboard, the health score and the AI context read from."""

    as_of: date

    # Balance sheet
    cash_assets: Decimal = ZERO
    investment_assets: Decimal = ZERO
    other_assets: Decimal = ZERO
    total_assets: Decimal = ZERO
    total_liabilities: Decimal = ZERO
    net_worth: Decimal = ZERO
    assets_basis: Basis = "profile"
    liabilities_basis: Basis = "profile"

    # Cash flow
    monthly_income: Decimal = ZERO
    monthly_expenses: Decimal = ZERO
    monthly_cash_flow: Decimal = ZERO
    essential_expenses: Decimal = ZERO
    discretionary_expenses: Decimal = ZERO
    income_basis: Basis = "profile"
    expense_basis: Basis = "profile"

    # Ratios
    savings_rate_pct: Decimal = ZERO
    debt_to_income_pct: Decimal = ZERO
    housing_ratio_pct: Decimal = ZERO
    emergency_fund: Decimal = ZERO
    emergency_fund_months: Decimal = ZERO
    emergency_fund_target: Decimal = ZERO

    # Debt
    total_debt: Decimal = ZERO
    monthly_minimum_payments: Decimal = ZERO
    weighted_avg_apr: Decimal = ZERO
    high_interest_debt: Decimal = ZERO
    debt_count: int = 0

    # Budget (current month)
    budget_total: Decimal = ZERO
    budget_spent: Decimal = ZERO
    budget_utilization_pct: Decimal = ZERO
    over_budget_categories: int = 0
    categories: list[CategorySpend] = field(default_factory=list)

    # Savings goals
    goals_target: Decimal = ZERO
    goals_saved: Decimal = ZERO
    goals_monthly_contribution: Decimal = ZERO
    goal_count: int = 0

    # Investments
    holdings_value: Decimal = ZERO
    holdings_cost_basis: Decimal = ZERO
    allocation_by_asset_type: dict = field(default_factory=dict)
    allocation_by_risk: dict = field(default_factory=dict)
    allocation_by_sector: dict = field(default_factory=dict)
    holding_count: int = 0

    # Profile context
    risk_tolerance: str = "moderate"
    investment_horizon_years: int = 10
    financial_goals: list = field(default_factory=list)
    has_profile: bool = False

    def to_dict(self) -> dict:
        out = {}
        for key, value in asdict(self).items():
            if key == "categories":
                out[key] = [c.to_dict() for c in self.categories]
            elif isinstance(value, Decimal):
                out[key] = float(value)
            elif isinstance(value, date):
                out[key] = value.isoformat()
            else:
                out[key] = value
        return out


# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

HIGH_INTEREST_APR = Decimal("8")  # above this, paying debt beats expected market return


def _trailing_transaction_flows(
    db: Session, user: User, as_of: date
) -> tuple[Decimal, Decimal, int, int]:
    """Average monthly income and expense over the trailing window."""
    window_start = (as_of.replace(day=1) - timedelta(days=1)).replace(day=1)
    for _ in range(TRAILING_MONTHS - 1):
        window_start = (window_start - timedelta(days=1)).replace(day=1)

    rows = db.scalars(
        select(Transaction).where(
            Transaction.user_id == user.id,
            Transaction.occurred_on >= window_start,
            Transaction.occurred_on <= as_of,
            Transaction.txn_type != TransactionType.TRANSFER.value,
        )
    ).all()

    income = total(t.amount for t in rows if t.txn_type == TransactionType.INCOME.value)
    expense = total(t.amount for t in rows if t.txn_type == TransactionType.EXPENSE.value)
    n_income = sum(1 for t in rows if t.txn_type == TransactionType.INCOME.value)
    n_expense = sum(1 for t in rows if t.txn_type == TransactionType.EXPENSE.value)

    divisor = Decimal(TRAILING_MONTHS)
    return money(income / divisor), money(expense / divisor), n_income, n_expense


def _spend_by_category(db: Session, user: User, start: date, end: date) -> dict[Optional[int], Decimal]:
    rows = db.scalars(
        select(Transaction).where(
            Transaction.user_id == user.id,
            Transaction.occurred_on >= start,
            Transaction.occurred_on <= end,
            Transaction.txn_type == TransactionType.EXPENSE.value,
        )
    ).all()
    out: dict[Optional[int], Decimal] = {}
    for t in rows:
        out[t.category_id] = out.get(t.category_id, ZERO) + D(t.amount)
    return {k: money(v) for k, v in out.items()}


def build_overview(db: Session, user: User, as_of: Optional[date] = None) -> Overview:
    as_of = as_of or date.today()
    ov = Overview(as_of=as_of)

    profile: Optional[FinancialProfile] = db.scalar(
        select(FinancialProfile).where(FinancialProfile.user_id == user.id)
    )
    ov.has_profile = profile is not None

    if profile:
        ov.risk_tolerance = profile.risk_tolerance
        ov.investment_horizon_years = profile.investment_horizon_years
        ov.financial_goals = list(profile.financial_goals or [])

    accounts = db.scalars(
        select(Account).where(Account.user_id == user.id, Account.is_active.is_(True))
    ).all()
    debts = db.scalars(select(Debt).where(Debt.user_id == user.id, Debt.is_active.is_(True))).all()
    goals = db.scalars(
        select(SavingsGoal).where(SavingsGoal.user_id == user.id, SavingsGoal.is_active.is_(True))
    ).all()
    holdings = db.scalars(
        select(InvestmentHolding).where(InvestmentHolding.user_id == user.id)
    ).all()

    # --- Assets --------------------------------------------------------
    cash_types = {
        AccountType.CHECKING.value,
        AccountType.SAVINGS.value,
        AccountType.CASH.value,
    }
    investment_account_types = {AccountType.INVESTMENT.value, AccountType.RETIREMENT.value}
    cash_accounts = [a for a in accounts if a.account_type in cash_types]

    if cash_accounts:
        ov.cash_assets = total(a.current_balance for a in cash_accounts)
        ov.assets_basis = "records"
    elif profile:
        ov.cash_assets = total(
            [profile.checking_balance, profile.savings_balance, profile.emergency_savings]
        )
        ov.assets_basis = "profile"

    if holdings:
        ov.holdings_value = total(h.market_value for h in holdings)
        ov.holdings_cost_basis = total(h.cost_basis for h in holdings if h.cost_basis is not None)
        ov.investment_assets = ov.holdings_value
        ov.holding_count = len(holdings)
    else:
        inv_accounts = [a for a in accounts if a.account_type in investment_account_types]
        if inv_accounts:
            ov.investment_assets = total(a.current_balance for a in inv_accounts)
        elif profile:
            ov.investment_assets = money(profile.investment_balance)

    ov.other_assets = total(
        a.current_balance
        for a in accounts
        if a.account_type == AccountType.OTHER.value and not a.is_liability
    )
    ov.total_assets = total([ov.cash_assets, ov.investment_assets, ov.other_assets])

    # --- Liabilities ---------------------------------------------------
    if debts:
        ov.total_debt = total(d.current_balance for d in debts)
        ov.monthly_minimum_payments = total(d.minimum_payment for d in debts)
        ov.debt_count = len(debts)
        ov.liabilities_basis = "records"
        balance_sum = ov.total_debt
        if balance_sum > 0:
            weighted = sum(D(d.current_balance) * D(d.apr) for d in debts)
            ov.weighted_avg_apr = rate(weighted / balance_sum)
        ov.high_interest_debt = total(
            d.current_balance for d in debts if D(d.apr) >= HIGH_INTEREST_APR
        )
    elif profile:
        ov.total_debt = money(profile.stated_total_debt)
        ov.monthly_minimum_payments = money(profile.stated_minimum_payments)
        ov.weighted_avg_apr = rate(profile.stated_debt_interest_rate)
        ov.high_interest_debt = (
            ov.total_debt if D(profile.stated_debt_interest_rate) >= HIGH_INTEREST_APR else ZERO
        )
        ov.liabilities_basis = "profile"

    credit_balances = total(
        abs(D(a.current_balance)) for a in accounts if a.is_liability and not debts
    )
    ov.total_liabilities = money(ov.total_debt + credit_balances)
    ov.net_worth = money(ov.total_assets - ov.total_liabilities)

    # --- Cash flow -----------------------------------------------------
    txn_income, txn_expense, n_inc, n_exp = _trailing_transaction_flows(db, user, as_of)

    if n_inc > 0:
        ov.monthly_income = txn_income
        ov.income_basis = "transactions"
    elif profile:
        ov.monthly_income = money(profile.total_monthly_income)
        ov.income_basis = "profile"

    if n_exp >= MIN_EXPENSE_TXNS_FOR_TRAILING:
        ov.monthly_expenses = txn_expense
        ov.expense_basis = "transactions"
    elif profile:
        ov.monthly_expenses = money(profile.total_monthly_expenses)
        ov.expense_basis = "profile"

    if profile:
        ov.essential_expenses = money(
            D(profile.monthly_housing_cost) + D(profile.monthly_essential_expenses)
        )
        ov.discretionary_expenses = money(profile.monthly_discretionary_expenses)
        ov.housing_ratio_pct = pct(profile.monthly_housing_cost, ov.monthly_income)

    ov.monthly_cash_flow = money(ov.monthly_income - ov.monthly_expenses)
    ov.savings_rate_pct = pct(ov.monthly_cash_flow, ov.monthly_income)
    ov.debt_to_income_pct = pct(ov.monthly_minimum_payments, ov.monthly_income)

    # --- Emergency fund ------------------------------------------------
    goal_emergency = total(
        g.current_amount for g in goals if g.goal_type == GoalType.EMERGENCY_FUND.value
    )
    profile_emergency = money(profile.emergency_savings) if profile else ZERO
    # Take the larger rather than the sum: a user typically records the same
    # pot in both places, and overstating the safety net is the worse error.
    ov.emergency_fund = max(goal_emergency, profile_emergency)
    baseline = ov.essential_expenses if ov.essential_expenses > 0 else ov.monthly_expenses
    ov.emergency_fund_months = (
        rate(safe_div(ov.emergency_fund, baseline)) if baseline > 0 else ZERO
    )
    ov.emergency_fund_target = money(baseline * 3)

    # --- Budget --------------------------------------------------------
    start, end = month_bounds(as_of.year, as_of.month)
    budget = db.scalar(
        select(MonthlyBudget).where(
            MonthlyBudget.user_id == user.id,
            MonthlyBudget.year == as_of.year,
            MonthlyBudget.month == as_of.month,
        )
    )
    spend = _spend_by_category(db, user, start, end)
    categories = db.scalars(
        select(BudgetCategory).where(
            BudgetCategory.user_id == user.id, BudgetCategory.is_archived.is_(False)
        ).order_by(BudgetCategory.sort_order, BudgetCategory.name)
    ).all()

    budgeted_by_cat: dict[int, Decimal] = {}
    if budget:
        for line in budget.lines:
            budgeted_by_cat[line.category_id] = D(line.budgeted_amount)

    rows: list[CategorySpend] = []
    for cat in categories:
        b = budgeted_by_cat.get(cat.id, ZERO)
        a = spend.get(cat.id, ZERO)
        if b == 0 and a == 0:
            continue
        rows.append(CategorySpend(cat.id, cat.name, cat.kind, money(b), money(a)))

    uncategorised = spend.get(None, ZERO)
    if uncategorised > 0:
        rows.append(
            CategorySpend(None, "Uncategorised", CategoryKind.OTHER.value, ZERO, uncategorised)
        )

    ov.categories = rows
    ov.budget_total = total(r.budgeted for r in rows)
    ov.budget_spent = total(r.actual for r in rows)
    ov.budget_utilization_pct = pct(ov.budget_spent, ov.budget_total)
    ov.over_budget_categories = sum(1 for r in rows if r.is_over)

    # --- Goals ---------------------------------------------------------
    ov.goals_target = total(g.target_amount for g in goals)
    ov.goals_saved = total(g.current_amount for g in goals)
    ov.goals_monthly_contribution = total(g.monthly_contribution for g in goals)
    ov.goal_count = len(goals)

    # --- Allocation ----------------------------------------------------
    if holdings and ov.holdings_value > 0:
        def _bucket(key_fn) -> dict:
            acc: dict[str, Decimal] = {}
            for h in holdings:
                key = key_fn(h) or "Unspecified"
                acc[key] = acc.get(key, ZERO) + h.market_value
            return {
                k: {"value": float(money(v)), "pct": float(pct(v, ov.holdings_value))}
                for k, v in sorted(acc.items(), key=lambda kv: kv[1], reverse=True)
            }

        ov.allocation_by_asset_type = _bucket(lambda h: h.asset_type)
        ov.allocation_by_risk = _bucket(lambda h: h.risk_category)
        ov.allocation_by_sector = _bucket(lambda h: h.sector)

    return ov
