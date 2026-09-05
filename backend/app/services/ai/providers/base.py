from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class AgentError(RuntimeError):
    """Raised when an agent cannot produce a valid response."""


@dataclass
class ProviderOutput:
    payload: dict
    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    raw: dict = field(default_factory=dict)


class AgentProvider(Protocol):
    name: str

    def run(self, agent: str, system_prompt: str, context: dict, model: str) -> ProviderOutput:
        ...
