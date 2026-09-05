"""SQLAlchemy models. Importing this package registers every mapper."""
from app.db.base import Base
from app.models.ai import AIRecommendation
from app.models.chat import ChatConversation, ChatMessage
from app.models.enums import (
    AccountType,
    AgentKind,
    AssetType,
    CategoryKind,
    DataSource,
    DebtType,
    GoalType,
    PayoffStrategy,
    RiskCategory,
    RiskTolerance,
    TransactionType,
)
from app.models.finance import (
    Account,
    BudgetCategory,
    BudgetLine,
    Debt,
    FinancialSnapshot,
    InvestmentHolding,
    MonthlyBudget,
    SavingsGoal,
    Transaction,
)
from app.models.user import FinancialProfile, PasswordResetToken, RefreshToken, User

__all__ = [
    "Base",
    "Account",
    "AccountType",
    "AgentKind",
    "AIRecommendation",
    "AssetType",
    "BudgetCategory",
    "ChatConversation",
    "ChatMessage",
    "BudgetLine",
    "CategoryKind",
    "DataSource",
    "Debt",
    "DebtType",
    "FinancialProfile",
    "FinancialSnapshot",
    "GoalType",
    "InvestmentHolding",
    "MonthlyBudget",
    "PasswordResetToken",
    "PayoffStrategy",
    "RefreshToken",
    "RiskCategory",
    "RiskTolerance",
    "SavingsGoal",
    "Transaction",
    "TransactionType",
    "User",
]
