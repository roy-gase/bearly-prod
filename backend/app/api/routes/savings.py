from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.core.deps import CurrentUser, DbSession, owned_or_404, owned_query
from app.models import GoalType, SavingsGoal
from app.schemas.finance import GoalContribution, GoalCreate, GoalOut, GoalUpdate
from app.services.ai.orchestrator import invalidate_for
from app.services.finance.metrics import build_overview
from app.services.finance.money import D, money, total
from app.services.finance.projections import emergency_fund_plan, goal_requirement

router = APIRouter(prefix="/savings", tags=["savings"])


def _serialise(goal: SavingsGoal) -> GoalOut:
    out = GoalOut.model_validate(goal)
    out.progress = goal_requirement(
        goal.target_amount, goal.current_amount, goal.target_date, goal.monthly_contribution
    )
    return out


@router.get("/goals", response_model=list[GoalOut])
def list_goals(user: CurrentUser, db: DbSession, include_inactive: bool = False):
    query = owned_query(SavingsGoal, user)
    if not include_inactive:
        query = query.where(SavingsGoal.is_active.is_(True))
    goals = db.scalars(query.order_by(SavingsGoal.priority, SavingsGoal.name)).all()
    return [_serialise(g) for g in goals]


@router.post("/goals", response_model=GoalOut, status_code=status.HTTP_201_CREATED)
def create_goal(payload: GoalCreate, user: CurrentUser, db: DbSession):
    goal = SavingsGoal(user_id=user.id, **payload.model_dump())
    db.add(goal)
    db.commit()
    db.refresh(goal)
    invalidate_for(db, user.id, "savings")
    return _serialise(goal)


@router.patch("/goals/{goal_id}", response_model=GoalOut)
def update_goal(goal_id: int, payload: GoalUpdate, user: CurrentUser, db: DbSession):
    goal = owned_or_404(db, SavingsGoal, goal_id, user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(goal, field, value)
    db.commit()
    db.refresh(goal)
    invalidate_for(db, user.id, "savings")
    return _serialise(goal)


@router.post("/goals/{goal_id}/contribute", response_model=GoalOut)
def contribute(goal_id: int, payload: GoalContribution, user: CurrentUser, db: DbSession):
    goal = owned_or_404(db, SavingsGoal, goal_id, user)
    goal.current_amount = money(D(goal.current_amount) + payload.amount)
    db.commit()
    db.refresh(goal)
    invalidate_for(db, user.id, "savings")
    return _serialise(goal)


@router.delete("/goals/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(goal_id: int, user: CurrentUser, db: DbSession) -> Response:
    goal = owned_or_404(db, SavingsGoal, goal_id, user)
    db.delete(goal)
    db.commit()
    invalidate_for(db, user.id, "savings")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/summary")
def summary(user: CurrentUser, db: DbSession) -> dict:
    ov = build_overview(db, user)
    goals = db.scalars(
        owned_query(SavingsGoal, user).where(SavingsGoal.is_active.is_(True))
    ).all()
    essentials = ov.essential_expenses if ov.essential_expenses > 0 else ov.monthly_expenses
    return {
        "total_target": float(total(g.target_amount for g in goals)),
        "total_saved": float(total(g.current_amount for g in goals)),
        "monthly_committed": float(total(g.monthly_contribution for g in goals)),
        "goal_count": len(goals),
        "on_track_count": sum(
            1
            for g in goals
            if goal_requirement(
                g.target_amount, g.current_amount, g.target_date, g.monthly_contribution
            )["on_track"]
            is True
        ),
        "monthly_surplus": float(ov.monthly_cash_flow),
        "emergency_fund": {
            "three_month": emergency_fund_plan(essentials, ov.emergency_fund, 3),
            "six_month": emergency_fund_plan(essentials, ov.emergency_fund, 6),
            "months_covered": float(ov.emergency_fund_months),
        },
    }
