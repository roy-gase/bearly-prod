from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession
from app.models import FinancialProfile
from app.schemas.finance import ProfileOut, ProfileUpdate
from app.services.ai.orchestrator import invalidate_for

router = APIRouter(prefix="/profile", tags=["profile"])


def _get_or_create(db, user) -> FinancialProfile:
    profile = db.scalar(select(FinancialProfile).where(FinancialProfile.user_id == user.id))
    if profile is None:
        profile = FinancialProfile(user_id=user.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


@router.get("", response_model=ProfileOut)
def get_profile(user: CurrentUser, db: DbSession) -> FinancialProfile:
    return _get_or_create(db, user)


@router.put("", response_model=ProfileOut)
def update_profile(payload: ProfileUpdate, user: CurrentUser, db: DbSession) -> FinancialProfile:
    profile = _get_or_create(db, user)
    for field, value in payload.model_dump().items():
        setattr(profile, field, value)
    if profile.onboarding_completed_at is None:
        profile.onboarding_completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(profile)
    # The profile feeds every metric, so every agent's answer is now stale.
    invalidate_for(db, user.id, "profile")
    return profile


@router.get("/status")
def onboarding_status(user: CurrentUser, db: DbSession) -> dict:
    profile = db.scalar(select(FinancialProfile).where(FinancialProfile.user_id == user.id))
    return {
        "has_profile": profile is not None,
        "completed": profile is not None and profile.onboarding_completed_at is not None,
        "completed_at": (
            profile.onboarding_completed_at.isoformat()
            if profile and profile.onboarding_completed_at
            else None
        ),
    }
