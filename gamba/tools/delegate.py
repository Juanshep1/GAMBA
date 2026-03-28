"""Delegate tool - allows agents to request help from other sub-agents.

This is the KEY feature of GAMBA. Sub-agents can call other sub-agents
directly, creating a hierarchy of autonomous workers. All delegation
events flow through the message bus so the user can watch in real-time.
"""

from __future__ import annotations

import asyncio
from typing import Any

from gamba.tools.base import BaseTool


class DelegateTool(BaseTool):
    name = "delegate"
    description = (
        "Delegate a task to another sub-agent. Pass the agent name and the task. "
        "The sub-agent will work autonomously and return its result."
    )
    inputs = {
        "agent_name": "Name of the agent to delegate to",
        "task": "The task description for the sub-agent",
    }
    output_type = "string"

    def __init__(self) -> None:
        super().__init__()
        self._orchestrator = None

    def bind_orchestrator(self, orchestrator: Any) -> None:
        """Bind the orchestrator so delegate can access other agents."""
        self._orchestrator = orchestrator

    def forward(self, agent_name: str, task: str, **kwargs: Any) -> str:
        if not self._orchestrator:
            return "Error: Delegate tool not bound to orchestrator"

        agent = self._orchestrator.agents.get(agent_name)
        if not agent:
            available = ", ".join(self._orchestrator.agents.keys())
            return f"Error: Agent '{agent_name}' not found. Available: {available}"

        # Run the sub-agent synchronously from within the sandbox
        try:
            loop = asyncio.get_running_loop()
            future = asyncio.ensure_future(agent.run(task))
            # We need to let the event loop process this
            # Use a thread to wait for the coroutine
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = pool.submit(lambda: asyncio.run(_run_agent(agent, task))).result(timeout=120)
            return result
        except RuntimeError:
            # No running loop - run directly
            return asyncio.run(_run_agent(agent, task))
        except Exception as e:
            return f"Error delegating to {agent_name}: {e}"


async def _run_agent(agent: Any, task: str) -> str:
    """Helper to run an agent in a new event loop."""
    return await agent.run(task)
