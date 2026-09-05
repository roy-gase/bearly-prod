from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import (
    AccountType,
    AssetType,
    CategoryKind,
    DebtType,
    GoalType,
    RiskCategory,
    RiskTolerance,
    TransactionType,
)

# Money arriving from the client is bounded so a typo cannot poison the maths.
Amount = Field(default=Decimal("0"), ge=Decimal("-1000000000"), le=Decimal("1000000000"))
PositiveAmount = Field(ge=Decimal("0"), le=Decimal("1000000000"))


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Profile ---------------------------------------------------------------


class ProfileBase(BaseModel):
    monthly_net_income: Decimal = Amount
    other_monthly_income: Decimal = Amount
    checking_balance: Decimal = Amount
    savings_balance: Decimal = Amount
    emergency_savings: Decimal = Amount
    investment_balance: Decimal = Amount
    monthly_housing_cost: Decimal = Amount
    monthly_essential_expenses: Decimal = Amount
    monthly_discretionary_expenses: Decimal = Amount
    stated_total_debt: Decimal = Amount
    stated_debt_interest_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    stated_minimum_payments: Decimal = Amount
    financial_goals: list[str] = Field(default_factory=list, max_length=12)
    investment_horizon_years: int = Field(default=10, ge=0, le=60)
    risk_tolerance: RiskTolerance = RiskTolerance.MODERATE
    notes: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("financial_goals")
    @classmethod
    def _clean_goals(cls, v: list[str]) -> list[str]:
        return [g.strip()[:120] for g in v if g and g.strip()]


class ProfileUpdate(ProfileBase):
    pass


class ProfileOut(ProfileBase, ORMModel):
    id: int
    onboarding_completed_at: Optional[datetime]
    updated_at: datetime


# --- Accounts --------------------------------------------------------------


class AccountBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    account_type: AccountType
    institution: Optional[str] = Field(default=None, max_length=120)
    current_balance: Decimal = Amount
    is_active: bool = True


class AccountCreate(AccountBase):
    pass


class AccountUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    account_type: Optional[AccountType] = None
    institution: Optional[str] = Field(default=None, max_length=120)
    current_balance: Optional[Decimal] = None
    is_active: Optional[bool] = None


class AccountOut(AccountBase, ORMModel):
    id: int
    source: str
    created_at: datetime


# --- Categories & budgets --------------------------------------------------


class CategoryBase(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    kind: CategoryKind = CategoryKind.OTHER
    icon: Optional[str] = Field(default=None, max_length=40)
    sort_order: int = 100


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=60)
    kind: Optional[CategoryKind] = None
    sort_order: Optional[int] = None
    is_archived: Optional[bool] = None


class CategoryOut(CategoryBase, ORMModel):
    id: int
    slug: str
    is_archived: bool


class BudgetLineIn(BaseModel):
    category_id: int
    budgeted_amount: Decimal = PositiveAmount


class BudgetUpsert(BaseModel):
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    expected_income: Decimal = Amount
    note: Optional[str] = Field(default=None, max_length=500)
    lines: list[BudgetLineIn] = Field(default_factory=list, max_length=60)


class BudgetLineOut(BaseModel):
    category_id: int
    name: str
    kind: str
    budgeted: float
    actual: float
    remaining: float
    used_pct: float
    is_over: bool


class BudgetOut(BaseModel):
    year: int
    month: int
    expected_income: float
    note: Optional[str]
    lines: list[BudgetLineOut]
    total_budgeted: float
    total_spent: float
    total_remaining: float
    utilization_pct: float
    total_income: float
    remaining_cash: float
    savings_rate_pct: float
    exists: bool


# --- Transactions ----------------------------------------------------------


class TransactionBase(BaseModel):
    occurred_on: date
    amount: Decimal = Field(gt=Decimal("0"), le=Decimal("1000000000"))
    merchant: str = Field(min_length=1, max_length=160)
    description: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = Field(default=None, max_length=1000)
    txn_type: TransactionType = TransactionType.EXPENSE
    account_id: Optional[int] = None
    transfer_account_id: Optional[int] = None
    category_id: Optional[int] = None

    @field_validator("occurred_on")
    @classmethod
    def _not_far_future(cls, v: date) -> date:
        if v.year > date.today().year + 1:
            raise ValueError("Date is too far in the future")
        return v


class TransactionCreate(TransactionBase):
    pass


class TransactionUpdate(BaseModel):
    occurred_on: Optional[date] = None
    amount: Optional[Decimal] = Field(default=None, gt=Decimal("0"))
    merchant: Optional[str] = Field(default=None, min_length=1, max_length=160)
    description: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = Field(default=None, max_length=1000)
    txn_type: Optional[TransactionType] = None
    account_id: Optional[int] = None
    transfer_account_id: Optional[int] = None
    category_id: Optional[int] = None


class TransactionOut(TransactionBase, ORMModel):
    id: int
    source: str
    category_name: Optional[str] = None
    account_name: Optional[str] = None


class TransactionPage(BaseModel):
    items: list[TransactionOut]
    total: int
    limit: int
    offset: int
    sum_income: float
    sum_expense: float


# --- Debts -----------------------------------------------------------------


class DebtBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    debt_type: DebtType = DebtType.OTHER
    current_balance: Decimal = PositiveAmount
    original_balance: Optional[Decimal] = None
    apr: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    minimum_payment: Decimal = PositiveAmount
    due_day: Optional[int] = Field(default=None, ge=1, le=31)
    notes: Optional[str] = Field(default=None, max_length=1000)


class DebtCreate(DebtBase):
    pass


class DebtUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    debt_type: Optional[DebtType] = None
    current_balance: Optional[Decimal] = Field(default=None, ge=0)
    apr: Optional[Decimal] = Field(default=None, ge=0, le=100)
    minimum_payment: Optional[Decimal] = Field(default=None, ge=0)
    due_day: Optional[int] = Field(default=None, ge=1, le=31)
    is_active: Optional[bool] = None
    notes: Optional[str] = Field(default=None, max_length=1000)


class DebtOut(DebtBase, ORMModel):
    id: int
    is_active: bool


# --- Savings ---------------------------------------------------------------


class GoalBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    goal_type: GoalType = GoalType.GENERAL
    target_amount: Decimal = PositiveAmount
    current_amount: Decimal = Field(default=Decimal("0"), ge=0)
    target_date: Optional[date] = None
    monthly_contribution: Decimal = Field(default=Decimal("0"), ge=0)
    priority: int = Field(default=3, ge=1, le=5)
    notes: Optional[str] = Field(default=None, max_length=1000)


class GoalCreate(GoalBase):
    pass


class GoalUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    goal_type: Optional[GoalType] = None
    target_amount: Optional[Decimal] = Field(default=None, ge=0)
    current_amount: Optional[Decimal] = Field(default=None, ge=0)
    target_date: Optional[date] = None
    monthly_contribution: Optional[Decimal] = Field(default=None, ge=0)
    priority: Optional[int] = Field(default=None, ge=1, le=5)
    is_active: Optional[bool] = None
    notes: Optional[str] = Field(default=None, max_length=1000)


class GoalOut(GoalBase, ORMModel):
    id: int
    is_active: bool
    progress: dict = Field(default_factory=dict)


class GoalContribution(BaseModel):
    amount: Decimal = Field(gt=Decimal("0"), le=Decimal("1000000000"))


# --- Investments -----------------------------------------------------------


class HoldingBase(BaseModel):
    ticker: Optional[str] = Field(default=None, max_length=20)
    name: str = Field(min_length=1, max_length=160)
    asset_type: AssetType = AssetType.OTHER
    quantity: Decimal = Field(default=Decimal("0"), ge=0)
    cost_basis: Optional[Decimal] = Field(default=None, ge=0)
    current_price: Optional[Decimal] = Field(default=None, ge=0)
    manual_value: Optional[Decimal] = Field(default=None, ge=0)
    sector: Optional[str] = Field(default=None, max_length=60)
    risk_category: RiskCategory = RiskCategory.MODERATE
    account_id: Optional[int] = None


class HoldingCreate(HoldingBase):
    pass


class HoldingUpdate(BaseModel):
    ticker: Optional[str] = Field(default=None, max_length=20)
    name: Optional[str] = Field(default=None, min_length=1, max_length=160)
    asset_type: Optional[AssetType] = None
    quantity: Optional[Decimal] = Field(default=None, ge=0)
    cost_basis: Optional[Decimal] = Field(default=None, ge=0)
    current_price: Optional[Decimal] = Field(default=None, ge=0)
    manual_value: Optional[Decimal] = Field(default=None, ge=0)
    sector: Optional[str] = Field(default=None, max_length=60)
    risk_category: Optional[RiskCategory] = None


class HoldingOut(HoldingBase, ORMModel):
    id: int
    market_value: float
    unrealized_gain: Optional[float]
    price_updated_at: Optional[datetime]
    price_source: Optional[str]


# --- AI --------------------------------------------------------------------


class AgentRunRequest(BaseModel):
    force_refresh: bool = False
    extra_payment: Optional[float] = Field(default=None, ge=0, le=1000000)


class PayoffRequest(BaseModel):
    extra_monthly: Decimal = Field(default=Decimal("0"), ge=0, le=Decimal("1000000"))


class ProjectionRequest(BaseModel):
    principal: Decimal = Field(default=Decimal("0"), ge=0)
    monthly_contribution: Decimal = Field(default=Decimal("0"), ge=0)
    annual_return_pct: Decimal = Field(default=Decimal("7"), ge=-20, le=30)
    years: int = Field(default=20, ge=1, le=60)
