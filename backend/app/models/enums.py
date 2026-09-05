"""Domain enumerations.

Stored as strings so a value is readable in the database and portable across
SQLite and PostgreSQL without a native ENUM type migration.
"""
from __future__ import annotations

import enum


class StrEnum(str, enum.Enum):
    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


class RiskTolerance(StrEnum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


class AccountType(StrEnum):
    CHECKING = "checking"
    SAVINGS = "savings"
    CREDIT_CARD = "credit_card"
    INVESTMENT = "investment"
    RETIREMENT = "retirement"
    LOAN = "loan"
    CASH = "cash"
    OTHER = "other"


class TransactionType(StrEnum):
    EXPENSE = "expense"
    INCOME = "income"
    TRANSFER = "transfer"


class CategoryKind(StrEnum):
    """How a budget category behaves in the cash-flow model."""

    ESSENTIAL = "essential"
    DISCRETIONARY = "discretionary"
    DEBT = "debt"
    SAVINGS = "savings"
    INVESTMENT = "investment"
    INCOME = "income"
    OTHER = "other"


class DebtType(StrEnum):
    CREDIT_CARD = "credit_card"
    AUTO_LOAN = "auto_loan"
    STUDENT_LOAN = "student_loan"
    PERSONAL_LOAN = "personal_loan"
    MORTGAGE = "mortgage"
    MEDICAL = "medical"
    OTHER = "other"


class PayoffStrategy(StrEnum):
    AVALANCHE = "avalanche"
    SNOWBALL = "snowball"
    MINIMUM_ONLY = "minimum_only"


class GoalType(StrEnum):
    EMERGENCY_FUND = "emergency_fund"
    VACATION = "vacation"
    HOUSE = "house"
    VEHICLE = "vehicle"
    EDUCATION = "education"
    WEDDING = "wedding"
    LARGE_PURCHASE = "large_purchase"
    GENERAL = "general"


class AssetType(StrEnum):
    STOCK = "stock"
    ETF = "etf"
    INDEX_FUND = "index_fund"
    MUTUAL_FUND = "mutual_fund"
    BOND = "bond"
    CASH = "cash"
    CRYPTO = "crypto"
    OTHER = "other"


class RiskCategory(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class AgentKind(StrEnum):
    BUDGET_COACH = "budget_coach"
    DEBT_STRATEGIST = "debt_strategist"
    SAVINGS_PLANNER = "savings_planner"
    INVESTMENT_RESEARCH = "investment_research"
    FINANCIAL_PLANNER = "financial_planner"


class DataSource(StrEnum):
    """Where a record came from. Bank/brokerage sync slots in here later."""

    MANUAL = "manual"
    IMPORT = "import"
    BANK_SYNC = "bank_sync"
    BROKERAGE_SYNC = "brokerage_sync"
