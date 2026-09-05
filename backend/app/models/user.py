from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Money, TimestampMixin, TZDateTime
from app.models.enums import RiskTolerance


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(120))
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(TZDateTime)
    # Brute-force protection. Stored rather than held in memory so the limit
    # applies across every gunicorn worker.
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[Optional[datetime]] = mapped_column(TZDateTime)

    profile: Mapped[Optional["FinancialProfile"]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.id}>"


class RefreshToken(Base):
    """Server-side refresh tokens so logout genuinely revokes a session."""

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(TZDateTime)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(TZDateTime)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)


class FinancialProfile(Base, TimestampMixin):
    """The onboarding snapshot of a user's situation.

    These are the user's own stated figures. Where transactions, debts, goals or
    holdings exist, the finance engine prefers those records and falls back to
    these values.
    """

    __tablename__ = "financial_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )

    monthly_net_income: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    other_monthly_income: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)

    checking_balance: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    savings_balance: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    emergency_savings: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    investment_balance: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)

    monthly_housing_cost: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    monthly_essential_expenses: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    monthly_discretionary_expenses: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)

    # Kept for users who onboard before entering individual debts.
    stated_total_debt: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    stated_debt_interest_rate: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    stated_minimum_payments: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)

    financial_goals: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    investment_horizon_years: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    risk_tolerance: Mapped[str] = mapped_column(
        String(20), default=RiskTolerance.MODERATE.value, nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(Text)

    onboarding_completed_at: Mapped[Optional[datetime]] = mapped_column(TZDateTime)

    user: Mapped["User"] = relationship(back_populates="profile")

    @property
    def total_monthly_income(self) -> Decimal:
        return (self.monthly_net_income or Decimal(0)) + (self.other_monthly_income or Decimal(0))

    @property
    def total_monthly_expenses(self) -> Decimal:
        return (
            (self.monthly_housing_cost or Decimal(0))
            + (self.monthly_essential_expenses or Decimal(0))
            + (self.monthly_discretionary_expenses or Decimal(0))
        )
