from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select

from app.core.deps import CurrentUser, DbSession, owned_or_404, owned_query
from app.models import Account, BudgetCategory, Transaction, TransactionType
from app.schemas.finance import (
    TransactionCreate,
    TransactionOut,
    TransactionPage,
    TransactionUpdate,
)
from app.services.ai.orchestrator import invalidate_for
from app.services.finance.money import total

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _validate_refs(db, user, payload) -> None:
    """A transaction may only point at the caller's own accounts and categories."""
    for field in ("account_id", "transfer_account_id"):
        value = getattr(payload, field, None)
        if value is not None:
            owned_or_404(db, Account, value, user)
    if getattr(payload, "category_id", None) is not None:
        owned_or_404(db, BudgetCategory, payload.category_id, user)


def _serialise(t: Transaction) -> TransactionOut:
    out = TransactionOut.model_validate(t)
    out.category_name = t.category.name if t.category else None
    out.account_name = t.account.name if t.account else None
    return out


@router.get("", response_model=TransactionPage)
def list_transactions(
    user: CurrentUser,
    db: DbSession,
    q: Optional[str] = Query(default=None, max_length=120),
    category_id: Optional[int] = None,
    account_id: Optional[int] = None,
    txn_type: Optional[TransactionType] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    min_amount: Optional[float] = Query(default=None, ge=0),
    max_amount: Optional[float] = Query(default=None, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    query = owned_query(Transaction, user)

    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(
            or_(
                Transaction.merchant.ilike(pattern),
                Transaction.description.ilike(pattern),
                Transaction.notes.ilike(pattern),
            )
        )
    if category_id is not None:
        query = query.where(Transaction.category_id == category_id)
    if account_id is not None:
        query = query.where(Transaction.account_id == account_id)
    if txn_type is not None:
        query = query.where(Transaction.txn_type == txn_type.value)
    if date_from is not None:
        query = query.where(Transaction.occurred_on >= date_from)
    if date_to is not None:
        query = query.where(Transaction.occurred_on <= date_to)
    if min_amount is not None:
        query = query.where(Transaction.amount >= min_amount)
    if max_amount is not None:
        query = query.where(Transaction.amount <= max_amount)

    matched = db.scalars(query).all()
    total_count = len(matched)
    page = db.scalars(
        query.order_by(Transaction.occurred_on.desc(), Transaction.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    return TransactionPage(
        items=[_serialise(t) for t in page],
        total=total_count,
        limit=limit,
        offset=offset,
        sum_income=float(
            total(t.amount for t in matched if t.txn_type == TransactionType.INCOME.value)
        ),
        sum_expense=float(
            total(t.amount for t in matched if t.txn_type == TransactionType.EXPENSE.value)
        ),
    )


@router.post("", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
def create_transaction(payload: TransactionCreate, user: CurrentUser, db: DbSession):
    _validate_refs(db, user, payload)
    if payload.txn_type == TransactionType.TRANSFER and payload.transfer_account_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A transfer needs a destination account",
        )
    txn = Transaction(user_id=user.id, **payload.model_dump())
    db.add(txn)
    db.commit()
    db.refresh(txn)
    invalidate_for(db, user.id, "transaction")
    return _serialise(txn)


@router.patch("/{txn_id}", response_model=TransactionOut)
def update_transaction(txn_id: int, payload: TransactionUpdate, user: CurrentUser, db: DbSession):
    txn = owned_or_404(db, Transaction, txn_id, user)
    _validate_refs(db, user, payload)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(txn, field, value)
    db.commit()
    db.refresh(txn)
    invalidate_for(db, user.id, "transaction")
    return _serialise(txn)


@router.delete("/{txn_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(txn_id: int, user: CurrentUser, db: DbSession) -> Response:
    txn = owned_or_404(db, Transaction, txn_id, user)
    db.delete(txn)
    db.commit()
    invalidate_for(db, user.id, "transaction")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
