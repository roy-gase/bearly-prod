"""Direct Claude inference from the API process.

Cost controls applied here:
- `output_config.format` constrains generation to the agent JSON schema, so no
  tokens are spent on prose that gets thrown away and no repair pass is needed.
- The system prompt is a fixed per-agent prefix and is cache-controlled, so
  repeat calls for the same agent only pay for the context.
- `max_tokens` is capped by BEARLY_AI_MAX_OUTPUT_TOKENS.
- Effort is set low for routine agents; only the planner runs higher.
"""
from __future__ import annotations

import json

from app.core.config import settings
from app.services.ai.prompts import PLANNING_AGENTS, user_message
from app.services.ai.providers.base import AgentError, ProviderOutput
from app.services.ai.schemas import AGENT_JSON_SCHEMA


class AnthropicProvider:
    name = "anthropic"

    def __init__(self) -> None:
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise AgentError("The `anthropic` package is not installed.") from exc
        if not settings.anthropic_api_key:
            raise AgentError("ANTHROPIC_API_KEY is not set.")
        self._client = anthropic.Anthropic(
            api_key=settings.anthropic_api_key, timeout=settings.ai_timeout_seconds
        )

    def run(self, agent: str, system_prompt: str, context: dict, model: str) -> ProviderOutput:
        effort = "high" if agent in PLANNING_AGENTS else "low"
        try:
            response = self._client.messages.create(
                model=model,
                max_tokens=settings.ai_max_output_tokens,
                system=[
                    {
                        "type": "text",
                        "text": system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": user_message(agent, context)}],
                output_config={
                    "effort": effort,
                    "format": {"type": "json_schema", "schema": AGENT_JSON_SCHEMA},
                },
                thinking={"type": "adaptive"},
            )
        except Exception as exc:  # noqa: BLE001 - surfaced as AgentError to the caller
            raise AgentError(f"Claude request failed: {type(exc).__name__}") from exc

        if getattr(response, "stop_reason", None) == "refusal":
            raise AgentError("The model declined to answer this request.")

        text = next((b.text for b in response.content if b.type == "text"), None)
        if not text:
            raise AgentError("Model returned no text content.")

        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AgentError("Model returned malformed JSON.") from exc

        usage = getattr(response, "usage", None)
        return ProviderOutput(
            payload=payload,
            model=model,
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
        )
