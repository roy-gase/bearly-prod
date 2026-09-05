from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Query, Response, status

from app.core.deps import CurrentUser, DbSession, owned_or_404, owned_query
from app.models import Debt, PayoffStrategy
from app.schemas.finance import DebtCreate, DebtOut, DebtUpdate, PayoffRequest
from app.services.ai.orchestrator import invalidate_for
from app.services.finance import debt as engine
from app.services.finance.metrics import build_overview
from app.services.finance.money import D, ZERO

router = APIRouter(prefix="/debts", tags=["debts"])


def _active_debts(db, user) -> list[Debt]:
    return list(
        db.scalars(owned_query(Debt, user).where(Debt.is_active.is_(True)).order_by(Debt.name)).all()
    )


@router.get("", response_model=list[DebtOut])
def list_debts(user: CurrentUser, db: DbSession, include_inactive: bool = False):
    query = owned_query(Debt, user)
    if not include_inactive:
        query = query.where(Debt.is_active.is_(True))
    return db.scalars(query.order_by(Debt.apr.desc())).all()


@router.post("", response_model=DebtOut, status_code=status.HTTP_201_CREATED)
def create_debt(payload: DebtCreate, user: CurrentUser, db: DbSession):
    debt = Debt(user_id=user.id, **payload.model_dump())
    db.add(debt)
    db.commit()
    db.refresh(debt)
    invalidate_for(db, user.id, "debt")
    return debt


@router.patch("/{debt_id}", response_model=DebtOut)
def update_debt(debt_id: int, payload: DebtUpdate, user: CurrentUser, db: DbSession):
    debt = owned_or_404(db, Debt, debt_id, user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(debt, field, value)
    db.commit()
    db.refresh(debt)
    invalidate_for(db, user.id, "debt")
    return debt


@router.delete("/{debt_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_debt(debt_id: int, user: CurrentUser, db: DbSession) -> Response:
    debt = owned_or_404(db, Debt, debt_id, user)
    db.delete(debt)
    db.commit()
    invalidate_for(db, user.id, "debt")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/summary")
def summary(user: CurrentUser, db: DbSession) -> dict:
    return engine.debt_summary(_active_debts(db, user))


@router.post("/payoff")
def payoff(payload: PayoffRequest, user: CurrentUser, db: DbSession) -> dict:
    """Avalanche vs snowball vs minimums, computed deterministically."""
    debts = [engine.DebtInput.from_model(d) for d in _active_debts(db, user)]
    ov = build_overview(db, user)
    extra = payload.extra_monthly
    if extra == 0:
        extra = max(ZERO, ov.monthly_cash_flow)
    result = engine.compare_strategies(debts, extra)
    result["summary"] = engine.debt_summary(_active_debts(db, user))
    result["suggested_extra_from_cash_flow"] = float(max(ZERO, ov.monthly_cash_flow))
    return result


@router.get("/payoff/{strategy}")
def payoff_single(
    strategy: PayoffStrategy,
    user: CurrentUser,
    db: DbSession,
    extra_monthly: float = Query(default=0, ge=0, le=1000000),
) -> dict:
    debts = [engine.DebtInput.from_model(d) for d in _active_debts(db, user)]
    return engine.simulate_payoff(debts, strategy.value, D(extra_monthly)).to_dict()
