from fastapi import APIRouter

from app.api.routes import (
    accounts,
    ai,
    auth,
    budgets,
    chat,
    dashboard,
    debts,
    investments,
    profile,
    savings,
    transactions,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth")
api_router.include_router(profile.router)
api_router.include_router(accounts.router)
api_router.include_router(transactions.router)
api_router.include_router(budgets.router)
api_router.include_router(debts.router)
api_router.include_router(savings.router)
api_router.include_router(investments.router)
api_router.include_router(dashboard.router)
api_router.include_router(ai.router)
api_router.include_router(chat.router)
