from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.config import settings
from app.core.deps import CurrentUser, DbSession, owned_query
from app.models import AgentKind, AIRecommendation
from app.schemas.finance import AgentRunRequest
from app.services.ai import orchestrator
from app.services.ai.prompts import AGENT_DESCRIPTIONS, AGENT_LABELS, PLANNING_AGENTS
from app.services.ai.schemas import AgentResult
from app.services.finance.metrics import build_overview

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/agents")
def list_agents(user: CurrentUser, db: DbSession) -> dict:
    """The agent catalogue, plus whether a fresh answer already exists.

    The frontend uses `has_fresh_result` to avoid triggering inference on page
    load — an agent only runs when the user asks for it.
    """
    ov = build_overview(db, user)
    agents = []
    for kind in AgentKind:
        latest = db.scalar(
            owned_query(AIRecommendation, user)
            .where(
                AIRecommendation.agent == kind.value,
                AIRecommendation.is_stale.is_(False),
            )
            .order_by(AIRecommendation.created_at.desc())
            .limit(1)
        )
        agents.append(
            {
                "key": kind.value,
                "label": AGENT_LABELS[kind.value],
                "description": AGENT_DESCRIPTIONS[kind.value],
                "tier": "planning" if kind.value in PLANNING_AGENTS else "routine",
                "unavailable_reason": orchestrator._skip_reason(kind.value, ov),
                "has_fresh_result": latest is not None,
                "last_generated_at": latest.created_at.isoformat() if latest else None,
            }
        )
    return {"agents": agents, "provider": settings.ai_provider}


@router.post("/agents/{agent}/run", response_model=AgentResult)
def run_agent(agent: str, payload: AgentRunRequest, user: CurrentUser, db: DbSession):
    """Run an agent. Served from cache unless the data changed or refresh is forced."""
    if agent not in orchestrator.VALID_AGENTS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown agent")
    extra = {"extra_payment": payload.extra_payment} if payload.extra_payment is not None else None
    return orchestrator.run_agent(
        db, user, agent, force_refresh=payload.force_refresh, extra=extra
    )


@router.get("/agents/{agent}/latest", response_model=Optional[AgentResult])
def latest_result(agent: str, user: CurrentUser, db: DbSession):
    """Read the stored answer without triggering inference."""
    if agent not in orchestrator.VALID_AGENTS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown agent")
    record = db.scalar(
        owned_query(AIRecommendation, user)
        .where(AIRecommendation.agent == agent, AIRecommendation.error.is_(None))
        .order_by(AIRecommendation.created_at.desc())
        .limit(1)
    )
    if record is None:
        return None
    return orchestrator._to_result(record, cached=True)


@router.get("/history")
def history(user: CurrentUser, db: DbSession, limit: int = 20) -> list[dict]:
    rows = db.scalars(
        owned_query(AIRecommendation, user)
        .order_by(AIRecommendation.created_at.desc())
        .limit(min(limit, 100))
    ).all()
    return [
        {
            "id": r.id,
            "agent": r.agent,
            "label": AGENT_LABELS.get(r.agent, r.agent),
            "summary": (r.payload or {}).get("summary", ""),
            "provider": r.provider,
            "model": r.model,
            "is_stale": r.is_stale,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.get("/usage")
def usage(user: CurrentUser, db: DbSession) -> dict:
    """Token spend and cache effectiveness, so cost is visible rather than assumed."""
    rows = db.scalars(owned_query(AIRecommendation, user)).all()
    billed = [r for r in rows if r.provider not in ("stub", "none")]
    return {
        "provider": settings.ai_provider,
        "routine_model": settings.ai_routine_model,
        "planner_model": settings.ai_planner_model,
        "cache_hours": settings.ai_cache_hours,
        "total_generations": len(rows),
        "billed_generations": len(billed),
        "input_tokens": sum(r.input_tokens for r in rows),
        "output_tokens": sum(r.output_tokens for r in rows),
        "avg_latency_ms": (
            int(sum(r.latency_ms for r in billed) / len(billed)) if billed else 0
        ),
    }
