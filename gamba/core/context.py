"""Minimal context builder - the anti-bloat layer.

Unlike OpenClaw (15-20K tokens injected per request), GAMBA caps system
prompts at ~800 tokens and uses a rolling 6-turn conversation window.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gamba.core.agent import Agent

MAX_SYSTEM_TOKENS = 800
MAX_HISTORY_TURNS = 6


def build_system_prompt(agent_name: str, agent_description: str, tool_names: list[str]) -> str:
    tools_str = ", ".join(tool_names) if tool_names else "none"
    return (
        f"You are {agent_name}. {agent_description}\n\n"
        f"Available tools: {tools_str}\n\n"
        "When you need to use a tool, write Python code in a ```python block.\n"
        "Call tools as functions: result = tool_name(arg1=val1, arg2=val2)\n"
        "When you have the final answer, write: FINAL_ANSWER: <your answer>"
    )


def build_messages(
    agent_name: str,
    agent_description: str,
    tool_names: list[str],
    history: list[dict],
    task: str,
) -> list[dict]:
    messages = [
        {"role": "system", "content": build_system_prompt(agent_name, agent_description, tool_names)}
    ]
    # Rolling window of recent history
    recent = history[-MAX_HISTORY_TURNS * 2:] if history else []
    messages.extend(recent)
    messages.append({"role": "user", "content": task})
    return messages
