"""Tool base class - SmolAgents-compatible interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    name: str = ""
    description: str = ""
    inputs: dict[str, str] = {}
    output_type: str = "string"

    @abstractmethod
    def forward(self, **kwargs: Any) -> Any: ...

    def __call__(self, **kwargs: Any) -> Any:
        return self.forward(**kwargs)

    def as_callable(self) -> tuple[str, Any]:
        """Return (name, callable) pair for sandbox injection."""
        return self.name, self.forward
