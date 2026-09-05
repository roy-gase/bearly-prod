from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Response, status

from app.core.deps import CurrentUser, DbSession, owned_or_404, owned_query
from app.models import Account, InvestmentHolding
from app.schemas.finance import HoldingCreate, HoldingOut, HoldingUpdate, ProjectionRequest
from app.services.ai.orchestrator import invalidate_for
from app.services.finance.metrics import build_overview
from app.services.finance.money import money, pct, total
from app.services.finance.priorities import build_priorities
from app.services.finance.projections import compound_growth

router = APIRouter(prefix="/investments", tags=["investments"])


def _serialise(h: InvestmentHolding) -> HoldingOut:
    out = HoldingOut.model_validate(h)
    out.market_value = float(h.market_value)
    gain = h.unrealized_gain
    out.unrealized_gain = float(gain) if gain is not None else None
    return out


@router.get("/holdings", response_model=list[HoldingOut])
def list_holdings(user: CurrentUser, db: DbSession):
    holdings = db.scalars(owned_query(InvestmentHolding, user).order_by(InvestmentHolding.name)).all()
    return sorted([_serialise(h) for h in holdings], key=lambda h: h.market_value, reverse=True)


@router.post("/holdings", response_model=HoldingOut, status_code=status.HTTP_201_CREATED)
def create_holding(payload: HoldingCreate, user: CurrentUser, db: DbSession):
    if payload.account_id is not None:
        owned_or_404(db, Account, payload.account_id, user)
    holding = InvestmentHolding(user_id=user.id, **payload.model_dump())
    if payload.current_price is not None:
        holding.price_updated_at = datetime.now(timezone.utc)
        holding.price_source = "manual"
    db.add(holding)
    db.commit()
    db.refresh(holding)
    invalidate_for(db, user.id, "investment")
    return _serialise(holding)


@router.patch("/holdings/{holding_id}", response_model=HoldingOut)
def update_holding(holding_id: int, payload: HoldingUpdate, user: CurrentUser, db: DbSession):
    holding = owned_or_404(db, InvestmentHolding, holding_id, user)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(holding, field, value)
    if "current_price" in data:
        holding.price_updated_at = datetime.now(timezone.utc)
        holding.price_source = "manual"
    db.commit()
    db.refresh(holding)
    invalidate_for(db, user.id, "investment")
    return _serialise(holding)


@router.delete("/holdings/{holding_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_holding(holding_id: int, user: CurrentUser, db: DbSession) -> Response:
    holding = owned_or_404(db, InvestmentHolding, holding_id, user)
    db.delete(holding)
    db.commit()
    invalidate_for(db, user.id, "investment")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/allocation")
def allocation(user: CurrentUser, db: DbSession) -> dict:
    ov = build_overview(db, user)
    priorities = build_priorities(ov)
    holdings = db.scalars(owned_query(InvestmentHolding, user)).all()
    cost_basis = total(h.cost_basis for h in holdings if h.cost_basis is not None)

    return {
        "total_value": float(ov.holdings_value),
        "cost_basis": float(cost_basis),
        "unrealized_gain": float(money(ov.holdings_value - cost_basis)) if cost_basis else None,
        "unrealized_gain_pct": float(pct(ov.holdings_value - cost_basis, cost_basis))
        if cost_basis
        else None,
        "holding_count": ov.holding_count,
        "by_asset_type": ov.allocation_by_asset_type,
        "by_risk": ov.allocation_by_risk,
        "by_sector": ov.allocation_by_sector,
        "risk_tolerance": ov.risk_tolerance,
        "horizon_years": ov.investment_horizon_years,
        # Investing is presented in the context of the whole plan, never alone.
        "readiness": {
            "investing_appropriate": priorities["investing_appropriate"],
            "blocked_reason": priorities["investing_blocked_reason"],
            "surplus_available_monthly": priorities["unallocated"],
        },
        "market_data": {
            "provider": None,
            "note": "Values are the amounts you entered. No market-data feed is connected.",
        },
    }


@router.post("/projection")
def projection(payload: ProjectionRequest, user: CurrentUser, db: DbSession) -> dict:
    result = compound_growth(
        payload.principal, payload.monthly_contribution, payload.annual_return_pct, payload.years
    )
    result["disclaimer"] = (
        "A projection at a fixed assumed rate, not a forecast. Real returns vary year to "
        "year and can be negative."
    )
    return result
