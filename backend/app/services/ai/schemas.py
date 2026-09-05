"""The contract every agent must satisfy.

Agent output is validated against this before it is stored or shown. A response
that does not parse is rejected rather than rendered — a finance product must
never display a half-formed recommendation.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Recommendation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    priority: int = Field(ge=1, le=10)
    title: str = Field(min_length=1, max_length=140)
    reason: str = Field(min_length=1, max_length=1200)
    suggested_amount: float = 0.0
    category: str = Field(default="general", max_length=60)

    @field_validator("suggested_amount", mode="before")
    @classmethod
    def _coerce_amount(cls, v):
        if v is None or v == "":
            return 0.0
        if isinstance(v, str):
            cleaned = v.replace("$", "").replace(",", "").strip()
            try:
                return float(cleaned)
            except ValueError:
                return 0.0
        return v


class AgentResponse(BaseModel):
    """The shape returned to the frontend for every agent."""

    model_config = ConfigDict(extra="ignore")

    summary: str = Field(min_length=1, max_length=1500)
    recommendations: list[Recommendation] = Field(default_factory=list, max_length=8)
    risks: list[str] = Field(default_factory=list, max_length=8)
    next_steps: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("recommendations")
    @classmethod
    def _sort_by_priority(cls, v: list[Recommendation]) -> list[Recommendation]:
        return sorted(v, key=lambda r: r.priority)

    @field_validator("risks", "next_steps", mode="before")
    @classmethod
    def _drop_empties(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return [str(item).strip() for item in v if str(item).strip()]


# JSON Schema handed to the model via output_config.format so the response is
# constrained at generation time rather than repaired afterwards.
AGENT_JSON_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "summary": {
            "type": "string",
            "description": "Two to four plain-language sentences on where the user stands.",
        },
        "recommendations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "priority": {"type": "integer", "description": "1 is most important."},
                    "title": {"type": "string"},
                    "reason": {
                        "type": "string",
                        "description": "Why this matters, citing the supplied figures.",
                    },
                    "suggested_amount": {
                        "type": "number",
                        "description": "Monthly dollar amount, or 0 if not applicable.",
                    },
                    "category": {"type": "string"},
                },
                "required": ["priority", "title", "reason", "suggested_amount", "category"],
                "additionalProperties": False,
            },
        },
        "risks": {"type": "array", "items": {"type": "string"}},
        "next_steps": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "recommendations", "risks", "next_steps"],
    "additionalProperties": False,
}


class AgentResult(BaseModel):
    """What the orchestrator returns: the response plus provenance."""

    agent: str
    response: AgentResponse
    provider: str
    model: Optional[str] = None
    cached: bool = False
    generated_at: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    # The exact figures the agent was given, so the UI can show its work.
    context_sent: dict = Field(default_factory=dict)
