"""Orchestrator - routes tasks to sub-agents and aggregates results.

The orchestrator is the brain. It:
1. Receives tasks from any interface via the message bus
2. Uses the LLM to decide which sub-agent(s) to delegate to
3. Runs sub-agents (possibly in parallel)
4. Aggregates and returns results
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from gamba.core.message_bus import MessageBus, EventType, Event
from gamba.core.agent import Agent
from gamba.providers.base import BaseProvider
from gamba.state.schemas import Config, AgentConfig
from gamba.state.store import StateStore
from gamba.config import load_agents


def create_provider(config: Config, provider_name: str = "") -> BaseProvider:
    """Create a provider instance from config."""
    name = provider_name or config.default_provider
    pconfig = config.providers.get(name)
    if not pconfig:
        raise ValueError(f"Provider '{name}' not configured. Run: python -m gamba --setup")

    if name == "openrouter":
        from gamba.providers.openrouter import OpenRouterProvider
        return OpenRouterProvider(api_key=pconfig.api_key, default_model=pconfig.default_model or "google/gemini-2.0-flash-001")
    elif name == "ollama":
        from gamba.providers.ollama import OllamaProvider
        return OllamaProvider(base_url=pconfig.base_url or "http://localhost:11434", default_model=pconfig.default_model or "llama3.2:3b")
    elif name == "huggingface":
        from gamba.providers.huggingface import HuggingFaceProvider
        return HuggingFaceProvider(api_token=pconfig.api_token, default_model=pconfig.default_model or "meta-llama/Llama-3.1-8B-Instruct")
    else:
        raise ValueError(f"Unknown provider: {name}")


class Orchestrator:
    """Routes tasks to sub-agents and aggregates results."""

    def __init__(self, config: Config, bus: MessageBus) -> None:
        self.config = config
        self.bus = bus
        self.store = StateStore(config.data_dir)
        self.agents: dict[str, Agent] = {}
        self.provider = create_provider(config)

        # Load agent definitions
        for agent_config in load_agents(config.agents_dir):
            agent_provider = create_provider(config, agent_config.provider) if agent_config.provider else self.provider
            self.agents[agent_config.name] = Agent(agent_config, bus, agent_provider, self.store)

        # Bind delegate tools so agents can call each other
        self._bind_delegate_tools()

        # Subscribe to user input
        bus.subscribe(EventType.USER_INPUT, self._handle_input)

    def _bind_delegate_tools(self) -> None:
        """Give each agent's delegate tool a reference to the orchestrator."""
        from gamba.tools.delegate import DelegateTool
        for agent in self.agents.values():
            for tool in agent.tools.values():
                if isinstance(tool, DelegateTool):
                    tool.bind_orchestrator(self)

    async def _handle_input(self, event: Event) -> None:
        message = event.data.get("message", "")
        if not message:
            return

        await self.bus.emit(EventType.SYSTEM_LOG, source="orchestrator", message=f"Received: {message[:100]}")

        # If no sub-agents configured, use the provider directly
        if not self.agents:
            await self._direct_response(message)
            return

        # Plan which agent(s) to use
        plan = await self._plan(message)

        if not plan:
            await self._direct_response(message)
            return

        # Execute agents
        await self.bus.emit(
            EventType.ORCHESTRATOR_PLAN, source="orchestrator",
            plan=plan, message=message[:100],
        )

        if len(plan) == 1:
            agent_name, task = plan[0]
            result = await self._run_agent(agent_name, task)
        else:
            # Run multiple agents in parallel
            tasks = [self._run_agent(name, task) for name, task in plan]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            result = await self._synthesize(message, [str(r) for r in results])

        await self.bus.emit(
            EventType.ORCHESTRATOR_RESPONSE, source="orchestrator",
            response=result,
        )

    async def _plan(self, message: str) -> list[tuple[str, str]]:
        """Use the LLM to decide which agent(s) should handle the task."""
        agent_descriptions = "\n".join(
            f"- {name}: {agent.config.description}"
            for name, agent in self.agents.items()
        )
        prompt = (
            f"Available agents:\n{agent_descriptions}\n\n"
            f"User request: {message}\n\n"
            "Which agent(s) should handle this? Respond with JSON array of "
            '[{"agent": "name", "task": "specific task"}]. '
            "If no agent fits, respond with an empty array []."
        )

        try:
            response = await self.provider.generate(
                [{"role": "user", "content": prompt}],
                model="",
                temperature=0.1,
                max_tokens=500,
            )
            # Extract JSON from response
            text = response.text.strip()
            # Handle markdown code blocks
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
            parsed = json.loads(text)
            return [(item["agent"], item["task"]) for item in parsed if item["agent"] in self.agents]
        except Exception:
            # Fallback: if only one agent, use it directly
            if len(self.agents) == 1:
                name = next(iter(self.agents))
                return [(name, message)]
            return []

    async def _run_agent(self, agent_name: str, task: str) -> str:
        agent = self.agents.get(agent_name)
        if not agent:
            return f"Agent '{agent_name}' not found"

        await self.bus.emit(
            EventType.AGENT_MESSAGE, source="orchestrator",
            target=agent_name, message=f"Delegating: {task[:100]}",
        )
        return await agent.run(task)

    async def _direct_response(self, message: str) -> None:
        """No agents configured - respond directly."""
        try:
            response = await self.provider.generate(
                [{"role": "user", "content": message}],
                model="",
            )
            await self.bus.emit(
                EventType.ORCHESTRATOR_RESPONSE, source="orchestrator",
                response=response.text,
            )
        except Exception as e:
            await self.bus.emit(
                EventType.ORCHESTRATOR_RESPONSE, source="orchestrator",
                response=f"Error: {e}",
            )

    async def _synthesize(self, original_message: str, results: list[str]) -> str:
        """Combine results from multiple agents."""
        combined = "\n\n---\n\n".join(f"Agent result {i+1}:\n{r}" for i, r in enumerate(results))
        prompt = (
            f"Original request: {original_message}\n\n"
            f"Agent results:\n{combined}\n\n"
            "Synthesize these results into a single coherent response."
        )
        try:
            response = await self.provider.generate(
                [{"role": "user", "content": prompt}],
                model="",
                max_tokens=2048,
            )
            return response.text
        except Exception:
            return combined

    async def shutdown(self) -> None:
        await self.provider.close()
        for agent in self.agents.values():
            await agent.provider.close()
