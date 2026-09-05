"""Create a demo account with realistic data.

Run with:  python seed_demo.py
Then sign in as demo@bearly.app / DemoPassw0rd!
"""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.db.session import SessionLocal, init_db
from app.models import (
    Account,
    BudgetCategory,
    BudgetLine,
    Debt,
    FinancialProfile,
    InvestmentHolding,
    MonthlyBudget,
    SavingsGoal,
    Transaction,
    User,
)
from app.core.security import hash_password
from app.services.seed import seed_default_categories

EMAIL = "demo@bearly.app"
PASSWORD = "DemoPassw0rd!"

MERCHANTS = {
    "Groceries": ["Whole Foods", "Trader Joe's", "Safeway", "Local Market"],
    "Restaurants": ["Ramen Bar", "Cafe Luna", "Taco Truck", "Sushi Ten"],
    "Transportation": ["Shell", "Metro Card", "Uber", "Chevron"],
    "Utilities": ["City Power", "Water Dept", "Comcast"],
    "Shopping": ["Amazon", "Target", "REI"],
    "Entertainment": ["Cinema 8", "Concert Hall", "Steam"],
    "Subscriptions": ["Netflix", "Spotify", "iCloud", "NYT"],
    "Healthcare": ["Dr Chen", "CVS Pharmacy"],
    "Housing": ["Sunset Apartments"],
    "Insurance": ["State Farm"],
}

TYPICAL = {
    "Groceries": (45, 160), "Restaurants": (18, 75), "Transportation": (25, 90),
    "Utilities": (60, 180), "Shopping": (30, 220), "Entertainment": (15, 80),
    "Subscriptions": (9, 20), "Healthcare": (20, 140), "Housing": (1850, 1850),
    "Insurance": (140, 140),
}


def main() -> None:
    init_db()
    db = SessionLocal()
    random.seed(7)

    existing = db.scalar(select(User).where(User.email == EMAIL))
    if existing:
        print(f"Demo user already exists (id={existing.id}). Delete bearly.db to reseed.")
        return

    user = User(email=EMAIL, hashed_password=hash_password(PASSWORD), full_name="Alex Rivera")
    db.add(user)
    db.flush()
    seed_default_categories(db, user)
    db.flush()

    db.add(
        FinancialProfile(
            user_id=user.id,
            monthly_net_income=Decimal("6200"),
            other_monthly_income=Decimal("450"),
            checking_balance=Decimal("3850"),
            savings_balance=Decimal("9200"),
            emergency_savings=Decimal("6800"),
            investment_balance=Decimal("0"),
            monthly_housing_cost=Decimal("1850"),
            monthly_essential_expenses=Decimal("1320"),
            monthly_discretionary_expenses=Decimal("980"),
            financial_goals=["Pay off debt", "Build an emergency fund", "Buy a home"],
            investment_horizon_years=20,
            risk_tolerance="moderate",
            onboarding_completed_at=datetime.now(timezone.utc),
        )
    )

    accounts = {}
    for name, kind, balance in [
        ("Everyday Checking", "checking", "3850"),
        ("High-Yield Savings", "savings", "9200"),
        ("Brokerage", "investment", "0"),
    ]:
        acct = Account(
            user_id=user.id, name=name, account_type=kind,
            institution="First National", current_balance=Decimal(balance),
        )
        db.add(acct)
        accounts[kind] = acct
    db.flush()

    for name, kind, balance, apr, minimum in [
        ("Sapphire Credit Card", "credit_card", "6840", "24.99", "205"),
        ("Store Card", "credit_card", "1150", "26.99", "38"),
        ("Auto Loan", "auto_loan", "13400", "6.40", "342"),
        ("Student Loan", "student_loan", "18900", "4.75", "210"),
    ]:
        db.add(
            Debt(
                user_id=user.id, name=name, debt_type=kind,
                current_balance=Decimal(balance), apr=Decimal(apr),
                minimum_payment=Decimal(minimum), due_day=random.randint(1, 28),
            )
        )

    today = date.today()
    for name, kind, target, current, months, monthly in [
        ("Emergency fund", "emergency_fund", "9510", "6800", 8, "350"),
        ("Japan trip", "vacation", "4500", "1200", 14, "220"),
        ("House deposit", "house", "40000", "5400", 48, "600"),
    ]:
        db.add(
            SavingsGoal(
                user_id=user.id, name=name, goal_type=kind,
                target_amount=Decimal(target), current_amount=Decimal(current),
                target_date=today + timedelta(days=months * 30),
                monthly_contribution=Decimal(monthly),
                priority=1 if kind == "emergency_fund" else 3,
            )
        )

    for ticker, name, kind, qty, price, cost, sector, risk in [
        ("VTI", "Vanguard Total Stock Market ETF", "etf", "22", "268.40", "5100", "Broad market", "moderate"),
        ("VXUS", "Vanguard Total International ETF", "etf", "40", "62.15", "2300", "International", "moderate"),
        ("BND", "Vanguard Total Bond ETF", "bond", "35", "73.80", "2650", "Fixed income", "low"),
        (None, "Company 401(k)", "index_fund", "1", "14200", "11800", "Retirement", "moderate"),
    ]:
        db.add(
            InvestmentHolding(
                user_id=user.id, account_id=accounts["investment"].id,
                ticker=ticker, name=name, asset_type=kind,
                quantity=Decimal(qty), current_price=Decimal(price),
                cost_basis=Decimal(cost), sector=sector, risk_category=risk,
                price_updated_at=datetime.now(timezone.utc), price_source="manual",
            )
        )

    categories = {
        c.name: c
        for c in db.scalars(select(BudgetCategory).where(BudgetCategory.user_id == user.id)).all()
    }

    # Four months of transactions.
    for months_back in range(4):
        year = today.year
        month = today.month - months_back
        while month <= 0:
            month += 12
            year -= 1
        last_day = 28 if months_back > 0 else min(today.day, 28)

        for day in (1, 15):
            if day <= last_day:
                db.add(
                    Transaction(
                        user_id=user.id, account_id=accounts["checking"].id,
                        occurred_on=date(year, month, day), amount=Decimal("3100"),
                        merchant="Northwind Systems — Payroll", txn_type="income",
                    )
                )

        for cat_name, merchants in MERCHANTS.items():
            category = categories.get(cat_name)
            if category is None:
                continue
            low, high = TYPICAL[cat_name]
            count = 1 if cat_name in ("Housing", "Insurance") else random.randint(2, 6)
            for _ in range(count):
                day = 1 if cat_name == "Housing" else random.randint(1, last_day)
                db.add(
                    Transaction(
                        user_id=user.id, account_id=accounts["checking"].id,
                        category_id=category.id, occurred_on=date(year, month, day),
                        amount=Decimal(str(round(random.uniform(low, high), 2))),
                        merchant=random.choice(merchants), txn_type="expense",
                    )
                )

    budget = MonthlyBudget(
        user_id=user.id, year=today.year, month=today.month, expected_income=Decimal("6650")
    )
    db.add(budget)
    db.flush()
    for cat_name, amount in [
        ("Housing", "1850"), ("Utilities", "260"), ("Groceries", "520"),
        ("Transportation", "220"), ("Insurance", "140"), ("Healthcare", "120"),
        ("Restaurants", "260"), ("Entertainment", "120"), ("Shopping", "220"),
        ("Subscriptions", "60"), ("Debt payments", "795"), ("Savings", "1170"),
    ]:
        category = categories.get(cat_name)
        if category:
            db.add(
                BudgetLine(budget_id=budget.id, category_id=category.id, budgeted_amount=Decimal(amount))
            )

    db.commit()
    print(f"Seeded demo account.\n  Email:    {EMAIL}\n  Password: {PASSWORD}")


if __name__ == "__main__":
    main()
