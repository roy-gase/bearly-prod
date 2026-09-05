"""Runs agents, caches their answers, and keeps inference spend down.

Cost controls, in the order they take effect:
  1. Gate  — some questions never need a model. If the deterministic engine
             already answers it, the agent is not called at all.
  2. Cache — a response is reused while the context fingerprint is unchanged
             and the entry has not expired. Editing finances changes the
             fingerprint, which invalidates it automatically.
  3. Tier  — routine agents run the cheap model; only planning runs the strong one.
  4. Cap   — output tokens are bounded, and the JSON schema stops the model
             writing anything that is not used.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import AgentKind, AIRecommendation, User
from app.services.ai import context as ctx_builder
from app.services.ai.prompts import PLANNING_AGENTS, PROMPTS
from app.services.ai.providers.base import AgentError, ProviderOutput
from app.services.ai.providers.stub import StubProvider
from app.services.ai.schemas import AgentResponse, AgentResult
from app.services.finance.metrics import Overview, build_overview

logger = logging.getLogger("bearly.ai")

VALID_AGENTS = {a.value for a in AgentKind}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_provider(name: str):
    """Resolve a provider, falling back to the stub if it cannot be constructed."""
    if name == "anthropic":
        from app.services.ai.providers.anthropic_provider import AnthropicProvider

        return AnthropicProvider()
    if name == "tenki":
        from app.services.ai.providers.tenki_provider import TenkiProvider

        return TenkiProvider()
    return StubProvider()


def _model_for(agent: str) -> str:
    return settings.ai_planner_model if agent in PLANNING_AGENTS else settings.ai_routine_model


def _skip_reason(agent: str, ov: Overview) -> Optional[str]:
    """Questions the finance engine already answers on its own.

    Calling a model here would cost money to restate a fact the user can see.
    """
    if not ov.has_profile:
        return "Complete your financial profile first so there is something to analyse."
    if agent == AgentKind.DEBT_STRATEGIST.value and ov.total_debt <= 0:
        return "You have no debt recorded, so there is no payoff strategy to compare."
    if agent == AgentKind.SAVINGS_PLANNER.value and ov.goal_count == 0 and ov.emergency_fund_months >= 6:
        return "Your emergency fund is fully funded and you have no other goals set."
    if agent == AgentKind.BUDGET_COACH.value and ov.monthly_income <= 0:
        return "Add your income before the Budget Coach can review your spending."
    return None


def _lookup_cached(
    db: Session, user: User, agent: str, fingerprint: str
) -> Optional[AIRecommendation]:
    return db.scalar(
        select(AIRecommendation)
        .where(
            AIRecommendation.user_id == user.id,
            AIRecommendation.agent == agent,
            AIRecommendation.input_fingerprint == fingerprint,
            AIRecommendation.is_stale.is_(False),
            AIRecommendation.error.is_(None),
            AIRecommendation.expires_at > _now(),
        )
        .order_by(AIRecommendation.created_at.desc())
        .limit(1)
    )


def _to_result(record: AIRecommendation, cached: bool) -> AgentResult:
    return AgentResult(
        agent=record.agent,
        response=AgentResponse.model_validate(record.payload),
        provider=record.provider,
        model=record.model,
        cached=cached,
        generated_at=record.created_at.isoformat(),
        input_tokens=record.input_tokens,
        output_tokens=record.output_tokens,
        latency_ms=record.latency_ms,
        context_sent=record.context_sent or {},
    )


def run_agent(
    db: Session,
    user: User,
    agent: str,
    *,
    force_refresh: bool = False,
    overview: Optional[Overview] = None,
    extra: Optional[dict] = None,
) -> AgentResult:
    if agent not in VALID_AGENTS:
        raise ValueError(f"Unknown agent: {agent}")

    ov = overview or build_overview(db, user)

    skip = _skip_reason(agent, ov)
    if skip:
        return AgentResult(
            agent=agent,
            response=AgentResponse(
                summary=skip,
                recommendations=[],
                risks=[],
                next_steps=["Add the missing information, then run this agent again."],
            ),
            provider="none",
            model=None,
            cached=False,
            generated_at=_now().isoformat(),
            context_sent={},
        )

    if agent == AgentKind.DEBT_STRATEGIST.value and extra:
        context = ctx_builder.build_debt_context(
            db, user, ov, extra_payment=extra.get("extra_payment", 0.0)
        )
    else:
        context = ctx_builder.build_context(db, user, agent, ov)

    fp = ctx_builder.fingerprint(context)

    if not force_refresh:
        cached = _lookup_cached(db, user, agent, fp)
        if cached is not None:
            return _to_result(cached, cached=True)

    provider_name = settings.ai_provider
    started = _now()
    fallback_note = None

    try:
        provider = _get_provider(provider_name)
        output: ProviderOutput = provider.run(
            agent, PROMPTS[agent], context, _model_for(agent)
        )
        used_provider = provider.name
    except AgentError as exc:
        # Never show the user an error page for a finance question the engine can
        # already answer. Fall back to deterministic guidance and say so.
        logger.warning("Agent %s failed on provider %s: %s", agent, provider_name, exc)
        output = StubProvider().run(agent, PROMPTS[agent], context, "deterministic")
        used_provider = "stub"
        fallback_note = (
            "Generated from Bearly's own calculations — the AI service was unavailable."
        )

    latency_ms = int((_now() - started).total_seconds() * 1000)

    try:
        response = AgentResponse.model_validate(output.payload)
    except ValidationError as exc:
        logger.warning("Agent %s returned an invalid response shape: %s", agent, exc.error_count())
        output = StubProvider().run(agent, PROMPTS[agent], context, "deterministic")
        response = AgentResponse.model_validate(output.payload)
        used_provider = "stub"
        fallback_note = "The AI response did not match the expected format, so this is calculated guidance."

    if fallback_note:
        response.risks = [*response.risks, fallback_note][:8]

    record = AIRecommendation(
        user_id=user.id,
        agent=agent,
        input_fingerprint=fp,
        payload=response.model_dump(),
        context_sent=context,
        provider=used_provider,
        model=output.model,
        input_tokens=output.input_tokens,
        output_tokens=output.output_tokens,
        latency_ms=latency_ms,
        created_at=started,
        expires_at=started + timedelta(hours=settings.ai_cache_hours),
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return _to_result(record, cached=False)


def invalidate(db: Session, user_id: int, agents: Optional[list[str]] = None) -> int:
    """Mark stored recommendations stale after the user's finances change.

    The fingerprint alone would handle correctness, but marking rows stale keeps
    the history table honest about what is still current.
    """
    query = select(AIRecommendation).where(
        AIRecommendation.user_id == user_id, AIRecommendation.is_stale.is_(False)
    )
    if agents:
        query = query.where(AIRecommendation.agent.in_(agents))
    rows = db.scalars(query).all()
    for row in rows:
        row.is_stale = True
    if rows:
        db.commit()
    return len(rows)


# Which agents care about which kind of change. Editing a debt should not
# invalidate the Budget Coach's answer.
INVALIDATION_MAP = {
    "profile": list(VALID_AGENTS),
    "transaction": [
        AgentKind.BUDGET_COACH.value,
        AgentKind.FINANCIAL_PLANNER.value,
    ],
    "budget": [AgentKind.BUDGET_COACH.value, AgentKind.FINANCIAL_PLANNER.value],
    "debt": [
        AgentKind.DEBT_STRATEGIST.value,
        AgentKind.FINANCIAL_PLANNER.value,
        AgentKind.INVESTMENT_RESEARCH.value,
    ],
    "savings": [
        AgentKind.SAVINGS_PLANNER.value,
        AgentKind.FINANCIAL_PLANNER.value,
        AgentKind.INVESTMENT_RESEARCH.value,
    ],
    "investment": [
        AgentKind.INVESTMENT_RESEARCH.value,
        AgentKind.FINANCIAL_PLANNER.value,
    ],
    "account": list(VALID_AGENTS),
}


def invalidate_for(db: Session, user_id: int, change: str) -> int:
    return invalidate(db, user_id, INVALIDATION_MAP.get(change))
