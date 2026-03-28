"""YAML config loader/saver."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from gamba.state.schemas import Config, AgentConfig


def load_config(config_path: str = "./data/config.yaml") -> Config:
    path = Path(config_path)
    if not path.exists():
        return Config()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return Config.model_validate(data)


def save_config(config: Config, config_path: str = "./data/config.yaml") -> None:
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(config.model_dump(), default_flow_style=False, sort_keys=False), encoding="utf-8")


def load_agents(agents_dir: str = "./agents") -> list[AgentConfig]:
    path = Path(agents_dir)
    if not path.exists():
        return []
    agents = []
    for yaml_file in sorted(path.glob("*.yaml")):
        data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
        agents.append(AgentConfig.model_validate(data))
    return agents


def save_agent(agent: AgentConfig, agents_dir: str = "./agents") -> None:
    path = Path(agents_dir)
    path.mkdir(parents=True, exist_ok=True)
    agent_path = path / f"{agent.name}.yaml"
    agent_path.write_text(yaml.dump(agent.model_dump(), default_flow_style=False, sort_keys=False), encoding="utf-8")
