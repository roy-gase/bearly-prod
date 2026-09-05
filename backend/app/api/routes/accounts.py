from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.core.deps import CurrentUser, DbSession, owned_or_404, owned_query
from app.models import Account
from app.schemas.finance import AccountCreate, AccountOut, AccountUpdate
from app.services.ai.orchestrator import invalidate_for

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountOut])
def list_accounts(user: CurrentUser, db: DbSession, include_inactive: bool = False):
    query = owned_query(Account, user)
    if not include_inactive:
        query = query.where(Account.is_active.is_(True))
    return db.scalars(query.order_by(Account.name)).all()


@router.post("", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
def create_account(payload: AccountCreate, user: CurrentUser, db: DbSession):
    account = Account(user_id=user.id, **payload.model_dump())
    db.add(account)
    db.commit()
    db.refresh(account)
    invalidate_for(db, user.id, "account")
    return account


@router.patch("/{account_id}", response_model=AccountOut)
def update_account(account_id: int, payload: AccountUpdate, user: CurrentUser, db: DbSession):
    account = owned_or_404(db, Account, account_id, user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(account, field, value)
    db.commit()
    db.refresh(account)
    invalidate_for(db, user.id, "account")
    return account


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(account_id: int, user: CurrentUser, db: DbSession) -> Response:
    account = owned_or_404(db, Account, account_id, user)
    db.delete(account)
    db.commit()
    invalidate_for(db, user.id, "account")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
