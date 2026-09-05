from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession, owned_or_404, owned_query
from app.models import BudgetCategory, BudgetLine, MonthlyBudget
from app.schemas.finance import (
    BudgetLineOut,
    BudgetOut,
    BudgetUpsert,
    CategoryCreate,
    CategoryOut,
    CategoryUpdate,
)
from app.services.ai.orchestrator import invalidate_for
from app.services.finance.metrics import build_overview
from app.services.finance.money import money, pct
from app.services.seed import slugify

router = APIRouter(prefix="/budgets", tags=["budgets"])


# --- Categories ------------------------------------------------------------


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(user: CurrentUser, db: DbSession, include_archived: bool = False):
    query = owned_query(BudgetCategory, user)
    if not include_archived:
        query = query.where(BudgetCategory.is_archived.is_(False))
    return db.scalars(query.order_by(BudgetCategory.sort_order, BudgetCategory.name)).all()


@router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(payload: CategoryCreate, user: CurrentUser, db: DbSession):
    slug = slugify(payload.name)
    existing = db.scalar(
        owned_query(BudgetCategory, user).where(BudgetCategory.slug == slug)
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="You already have a category with that name"
        )
    category = BudgetCategory(user_id=user.id, slug=slug, **payload.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.patch("/categories/{category_id}", response_model=CategoryOut)
def update_category(category_id: int, payload: CategoryUpdate, user: CurrentUser, db: DbSession):
    category = owned_or_404(db, BudgetCategory, category_id, user)
    data = payload.model_dump(exclude_unset=True)
    if "name" in data:
        category.slug = slugify(data["name"])
    for field, value in data.items():
        setattr(category, field, value)
    db.commit()
    db.refresh(category)
    invalidate_for(db, user.id, "budget")
    return category


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_category(category_id: int, user: CurrentUser, db: DbSession) -> Response:
    """Archive rather than delete so historical transactions keep their label."""
    category = owned_or_404(db, BudgetCategory, category_id, user)
    category.is_archived = True
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Monthly budget --------------------------------------------------------


@router.get("", response_model=BudgetOut)
def get_budget(
    user: CurrentUser,
    db: DbSession,
    year: int = Query(default=None, ge=2000, le=2100),
    month: int = Query(default=None, ge=1, le=12),
):
    today = date.today()
    year = year or today.year
    month = month or today.month

    budget = db.scalar(
        owned_query(MonthlyBudget, user).where(
            MonthlyBudget.year == year, MonthlyBudget.month == month
        )
    )
    ov = build_overview(db, user, as_of=date(year, month, min(today.day, 28)))

    lines = [
        BudgetLineOut(
            category_id=c.category_id or 0,
            name=c.name,
            kind=c.kind,
            budgeted=float(c.budgeted),
            actual=float(c.actual),
            remaining=float(c.remaining),
            used_pct=float(c.used_pct),
            is_over=c.is_over,
        )
        for c in ov.categories
    ]

    expected_income = (
        float(money(budget.expected_income)) if budget and budget.expected_income else float(ov.monthly_income)
    )
    remaining_cash = money(expected_income - float(ov.budget_spent))

    return BudgetOut(
        year=year,
        month=month,
        expected_income=expected_income,
        note=budget.note if budget else None,
        lines=lines,
        total_budgeted=float(ov.budget_total),
        total_spent=float(ov.budget_spent),
        total_remaining=float(money(ov.budget_total - ov.budget_spent)),
        utilization_pct=float(ov.budget_utilization_pct),
        total_income=expected_income,
        remaining_cash=float(remaining_cash),
        savings_rate_pct=float(pct(remaining_cash, expected_income)),
        exists=budget is not None,
    )


@router.put("", response_model=BudgetOut)
def upsert_budget(payload: BudgetUpsert, user: CurrentUser, db: DbSession):
    budget = db.scalar(
        owned_query(MonthlyBudget, user).where(
            MonthlyBudget.year == payload.year, MonthlyBudget.month == payload.month
        )
    )
    if budget is None:
        budget = MonthlyBudget(user_id=user.id, year=payload.year, month=payload.month)
        db.add(budget)
        db.flush()

    budget.expected_income = payload.expected_income
    budget.note = payload.note

    # Every referenced category must belong to the caller.
    owned_ids = {
        c.id for c in db.scalars(owned_query(BudgetCategory, user)).all()
    }
    for line in payload.lines:
        if line.category_id not in owned_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Category {line.category_id} not found",
            )

    existing = {line.category_id: line for line in budget.lines}
    submitted = {line.category_id for line in payload.lines}

    for line in payload.lines:
        if line.category_id in existing:
            existing[line.category_id].budgeted_amount = line.budgeted_amount
        else:
            db.add(
                BudgetLine(
                    budget_id=budget.id,
                    category_id=line.category_id,
                    budgeted_amount=line.budgeted_amount,
                )
            )
    for category_id, line in existing.items():
        if category_id not in submitted:
            db.delete(line)

    db.commit()
    invalidate_for(db, user.id, "budget")
    return get_budget(user, db, year=payload.year, month=payload.month)


@router.post("/copy-previous", response_model=BudgetOut)
def copy_previous_month(
    user: CurrentUser,
    db: DbSession,
    year: int = Query(ge=2000, le=2100),
    month: int = Query(ge=1, le=12),
):
    """Start this month from last month's plan rather than a blank page."""
    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    source = db.scalar(
        owned_query(MonthlyBudget, user).where(
            MonthlyBudget.year == prev_year, MonthlyBudget.month == prev_month
        )
    )
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No budget found for the previous month"
        )
    payload = BudgetUpsert(
        year=year,
        month=month,
        expected_income=source.expected_income,
        note=source.note,
        lines=[
            {"category_id": line.category_id, "budgeted_amount": line.budgeted_amount}
            for line in source.lines
        ],
    )
    return upsert_budget(payload, user, db)
