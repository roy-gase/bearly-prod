from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Money, Qty, Rate, TimestampMixin, TZDateTime
from app.models.enums import (
    AccountType,
    AssetType,
    CategoryKind,
    DataSource,
    DebtType,
    GoalType,
    RiskCategory,
    TransactionType,
)


class Account(Base, TimestampMixin):
    """A place money sits. Manual today; `external_id`/`source` let a bank or
    brokerage connector attach to the same rows later without a redesign."""

    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    account_type: Mapped[str] = mapped_column(String(30), nullable=False)
    institution: Mapped[Optional[str]] = mapped_column(String(120))
    current_balance: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    source: Mapped[str] = mapped_column(String(20), default=DataSource.MANUAL.value, nullable=False)
    external_id: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    provider: Mapped[Optional[str]] = mapped_column(String(50))
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(TZDateTime)

    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="account", cascade="all, delete-orphan", foreign_keys="Transaction.account_id"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "provider", "external_id", name="uq_account_external"),
    )

    @property
    def is_liability(self) -> bool:
        return self.account_type in (AccountType.CREDIT_CARD.value, AccountType.LOAN.value)


class BudgetCategory(Base, TimestampMixin):
    """A user's category catalogue. Seeded with sensible defaults at signup."""

    __tablename__ = "budget_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    slug: Mapped[str] = mapped_column(String(60), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), default=CategoryKind.OTHER.value, nullable=False)
    icon: Mapped[Optional[str]] = mapped_column(String(40))
    sort_order: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "slug", name="uq_category_slug_per_user"),)


class MonthlyBudget(Base, TimestampMixin):
    """One budget per user per calendar month."""

    __tablename__ = "monthly_budgets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_income: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text)

    lines: Mapped[list["BudgetLine"]] = relationship(
        back_populates="budget", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (UniqueConstraint("user_id", "year", "month", name="uq_budget_period"),)


class BudgetLine(Base, TimestampMixin):
    __tablename__ = "budget_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    budget_id: Mapped[int] = mapped_column(
        ForeignKey("monthly_budgets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    category_id: Mapped[int] = mapped_column(
        ForeignKey("budget_categories.id", ondelete="CASCADE"), nullable=False
    )
    budgeted_amount: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)

    budget: Mapped["MonthlyBudget"] = relationship(back_populates="lines")
    category: Mapped["BudgetCategory"] = relationship(lazy="joined")

    __table_args__ = (UniqueConstraint("budget_id", "category_id", name="uq_budget_line"),)


class Transaction(Base, TimestampMixin):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    account_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL")
    )
    # For transfers: the account money landed in.
    transfer_account_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL")
    )
    category_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("budget_categories.id", ondelete="SET NULL"), index=True
    )

    occurred_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    # Always stored positive; `txn_type` carries the direction.
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    merchant: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    txn_type: Mapped[str] = mapped_column(String(20), nullable=False)

    source: Mapped[str] = mapped_column(String(20), default=DataSource.MANUAL.value, nullable=False)
    external_id: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    is_pending: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    account: Mapped[Optional["Account"]] = relationship(
        back_populates="transactions", foreign_keys=[account_id]
    )
    category: Mapped[Optional["BudgetCategory"]] = relationship(lazy="joined")

    __table_args__ = (
        Index("ix_txn_user_date", "user_id", "occurred_on"),
        Index("ix_txn_user_type_date", "user_id", "txn_type", "occurred_on"),
        UniqueConstraint("user_id", "external_id", name="uq_txn_external"),
    )

    @property
    def signed_amount(self) -> Decimal:
        """Positive for income, negative for expense, zero net for transfers."""
        if self.txn_type == TransactionType.INCOME.value:
            return self.amount
        if self.txn_type == TransactionType.EXPENSE.value:
            return -self.amount
        return Decimal(0)


class Debt(Base, TimestampMixin):
    __tablename__ = "debts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    debt_type: Mapped[str] = mapped_column(String(30), default=DebtType.OTHER.value, nullable=False)
    current_balance: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    original_balance: Mapped[Optional[Decimal]] = mapped_column(Money)
    apr: Mapped[Decimal] = mapped_column(Rate, default=0, nullable=False)
    minimum_payment: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    due_day: Mapped[Optional[int]] = mapped_column(Integer)
    account_id: Mapped[Optional[int]] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)


class SavingsGoal(Base, TimestampMixin):
    __tablename__ = "savings_goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    goal_type: Mapped[str] = mapped_column(String(30), default=GoalType.GENERAL.value, nullable=False)
    target_amount: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    current_amount: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    target_date: Mapped[Optional[date]] = mapped_column(Date)
    monthly_contribution: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    account_id: Mapped[Optional[int]] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)


class InvestmentHolding(Base, TimestampMixin):
    """Manual holdings today. `current_price`/`price_updated_at` are the seam a
    market-data provider fills in later."""

    __tablename__ = "investment_holdings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    account_id: Mapped[Optional[int]] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"))

    ticker: Mapped[Optional[str]] = mapped_column(String(20), index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(20), default=AssetType.OTHER.value, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Qty, default=0, nullable=False)
    cost_basis: Mapped[Optional[Decimal]] = mapped_column(Money)
    current_price: Mapped[Optional[Decimal]] = mapped_column(Money)
    # Set directly when the user has no per-share price (e.g. a 401k balance).
    manual_value: Mapped[Optional[Decimal]] = mapped_column(Money)
    sector: Mapped[Optional[str]] = mapped_column(String(60))
    risk_category: Mapped[str] = mapped_column(
        String(20), default=RiskCategory.MODERATE.value, nullable=False
    )
    price_updated_at: Mapped[Optional[datetime]] = mapped_column(TZDateTime)
    price_source: Mapped[Optional[str]] = mapped_column(String(40))

    @property
    def market_value(self) -> Decimal:
        if self.manual_value is not None:
            return self.manual_value
        if self.current_price is not None:
            return (self.quantity or Decimal(0)) * self.current_price
        return self.cost_basis or Decimal(0)

    @property
    def unrealized_gain(self) -> Optional[Decimal]:
        if self.cost_basis is None:
            return None
        return self.market_value - self.cost_basis


class FinancialSnapshot(Base):
    """A dated record of the headline metrics so progress can be charted."""

    __tablename__ = "financial_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    captured_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    net_worth: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    total_assets: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    total_liabilities: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    monthly_income: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    monthly_expenses: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    monthly_cash_flow: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    savings_rate: Mapped[Decimal] = mapped_column(Rate, default=0, nullable=False)
    emergency_fund_months: Mapped[Decimal] = mapped_column(Rate, default=0, nullable=False)
    debt_to_income: Mapped[Decimal] = mapped_column(Rate, default=0, nullable=False)
    health_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    detail: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "captured_on", name="uq_snapshot_per_day"),)
