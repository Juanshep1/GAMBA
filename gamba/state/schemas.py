"""Pydantic models for config and state."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProviderConfig(BaseModel):
    api_key: str = ""
    api_token: str = ""
    base_url: str = ""
    default_model: str = ""


class InterfaceConfig(BaseModel):
    enabled: bool = False
    bot_token: str = ""
    port: int = 8420


class Config(BaseModel):
    version: int = 1
    default_provider: str = "openrouter"
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    interfaces: dict[str, InterfaceConfig] = Field(default_factory=lambda: {
        "tui": InterfaceConfig(enabled=True),
        "discord": InterfaceConfig(),
        "telegram": InterfaceConfig(),
        "web": InterfaceConfig(port=8420),
    })
    agents_dir: str = "./agents"
    data_dir: str = "./data"


class AgentConfig(BaseModel):
    name: str
    description: str = "A helpful agent"
    provider: str = ""  # empty = use default
    model: str = ""  # empty = use provider default
    tools: list[str] = Field(default_factory=lambda: ["web_search", "file_read"])
    autonomy: str = "full"
    max_steps: int = 15
    temperature: float = 0.7
    system_prompt: str = ""
