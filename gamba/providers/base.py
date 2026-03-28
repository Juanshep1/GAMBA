"""Abstract AI provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMResponse:
    text: str
    usage: dict[str, int] = field(default_factory=dict)
    model: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


class BaseProvider(ABC):
    """All providers implement this. Raw HTTP, no SDK bloat."""

    @abstractmethod
    async def generate(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse: ...

    @abstractmethod
    async def close(self) -> None: ...
