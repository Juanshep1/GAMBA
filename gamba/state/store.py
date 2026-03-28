"""File-based JSON state manager. No database needed."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class StateStore:
    """Simple file-based state persistence per agent."""

    def __init__(self, data_dir: str = "./data") -> None:
        self.data_dir = Path(data_dir)
        self.state_dir = self.data_dir / "state"
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def _agent_path(self, agent_name: str) -> Path:
        return self.state_dir / f"{agent_name}.json"

    def load(self, agent_name: str) -> dict[str, Any]:
        path = self._agent_path(agent_name)
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return {"history": [], "metadata": {}}

    def save(self, agent_name: str, state: dict[str, Any]) -> None:
        path = self._agent_path(agent_name)
        path.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")

    def append_history(self, agent_name: str, role: str, content: str) -> None:
        state = self.load(agent_name)
        state["history"].append({"role": role, "content": content})
        # Keep history bounded
        if len(state["history"]) > 100:
            state["history"] = state["history"][-50:]
        self.save(agent_name, state)

    def get_history(self, agent_name: str) -> list[dict[str, str]]:
        return self.load(agent_name).get("history", [])

    def clear(self, agent_name: str) -> None:
        path = self._agent_path(agent_name)
        if path.exists():
            path.unlink()
