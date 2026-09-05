"""Default budget categories, created for every new account."""
from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.models import BudgetCategory, CategoryKind, User

DEFAULT_CATEGORIES: list[tuple[str, CategoryKind, str]] = [
    ("Housing", CategoryKind.ESSENTIAL, "home"),
    ("Utilities", CategoryKind.ESSENTIAL, "zap"),
    ("Groceries", CategoryKind.ESSENTIAL, "shopping-cart"),
    ("Transportation", CategoryKind.ESSENTIAL, "car"),
    ("Insurance", CategoryKind.ESSENTIAL, "shield"),
    ("Healthcare", CategoryKind.ESSENTIAL, "heart-pulse"),
    ("Restaurants", CategoryKind.DISCRETIONARY, "utensils"),
    ("Entertainment", CategoryKind.DISCRETIONARY, "clapperboard"),
    ("Shopping", CategoryKind.DISCRETIONARY, "shopping-bag"),
    ("Subscriptions", CategoryKind.DISCRETIONARY, "repeat"),
    ("Travel", CategoryKind.DISCRETIONARY, "plane"),
    ("Debt payments", CategoryKind.DEBT, "credit-card"),
    ("Savings", CategoryKind.SAVINGS, "piggy-bank"),
    ("Investments", CategoryKind.INVESTMENT, "trending-up"),
    ("Other", CategoryKind.OTHER, "circle-dashed"),
]


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60]


def seed_default_categories(db: Session, user: User) -> list[BudgetCategory]:
    created = []
    for order, (name, kind, icon) in enumerate(DEFAULT_CATEGORIES):
        category = BudgetCategory(
            user_id=user.id,
            name=name,
            slug=slugify(name),
            kind=kind.value,
            icon=icon,
            sort_order=order * 10,
        )
        db.add(category)
        created.append(category)
    db.flush()
    return created
