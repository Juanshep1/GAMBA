"""Agent - autonomous unit with ReAct loop and tool execution.

Each agent runs a think-act-observe loop:
1. Build minimal context
2. Call LLM
3. Parse response for code blocks or final answer
4. Execute code (which calls tools)
5. Feed result back into context
6. Repeat until final answer or max steps
"""

from __future__ import annotations

import re
from typing import Any

from gamba.core.message_bus import MessageBus, EventType
from gamba.core.context import build_messages
from gamba.core.sandbox import execute
from gamba.providers.base import BaseProvider
from gamba.state.schemas import AgentConfig
from gamba.state.store import StateStore
from gamba.tools.base import BaseTool

CODE_BLOCK_RE = re.compile(r"```python\s*\n(.*?)```", re.DOTALL)
FINAL_ANSWER_RE = re.compile(r"FINAL_ANSWER:\s*(.*)", re.DOTALL)

# Registry of all built-in tools
TOOL_REGISTRY: dict[str, type[BaseTool]] = {}


def register_tools() -> None:
    """Lazy-load and register all built-in tools."""
    if TOOL_REGISTRY:
        return
    from gamba.tools.web_search import WebSearchTool
    from gamba.tools.file_io import FileReadTool, FileWriteTool, FileListTool
    from gamba.tools.code_exec import CodeExecTool
    from gamba.tools.shell import ShellTool
    from gamba.tools.http_request import HttpRequestTool
    from gamba.tools.video_search import VideoSearchTool
    from gamba.tools.delegate import DelegateTool

    for cls in [WebSearchTool, VideoSearchTool, FileReadTool, FileWriteTool, FileListTool, CodeExecTool, ShellTool, HttpRequestTool, DelegateTool]:
        TOOL_REGISTRY[cls.name] = cls


class Agent:
    """A single autonomous agent."""

    def __init__(
        self,
        config: AgentConfig,
        bus: MessageBus,
        provider: BaseProvider,
        store: StateStore,
    ) -> None:
        self.config = config
        self.bus = bus
        self.provider = provider
        self.store = store
        self.tools: dict[str, BaseTool] = {}
        self._load_tools()

    def _load_tools(self) -> None:
        register_tools()
        for tool_name in self.config.tools:
            if tool_name in TOOL_REGISTRY:
                self.tools[tool_name] = TOOL_REGISTRY[tool_name]()

    async def run(self, task: str) -> str:
        """Execute a task autonomously using a ReAct-style loop."""
        await self.bus.emit(
            EventType.AGENT_SPAWNED, source=self.config.name,
            task=task,
        )

        history: list[dict[str, str]] = []
        tool_callables = {name: tool.forward for name, tool in self.tools.items()}
        description = self.config.system_prompt or self.config.description

        for step in range(self.config.max_steps):
            messages = build_messages(
                agent_name=self.config.name,
                agent_description=description,
                tool_names=list(self.tools.keys()),
                history=history,
                task=task if step == 0 else f"Previous step result is in the conversation. Continue working on: {task}",
            )

            try:
                response = await self.provider.generate(
                    messages,
                    model=self.config.model,
                    temperature=self.config.temperature,
                )
            except Exception as e:
                await self.bus.emit(
                    EventType.AGENT_ERROR, source=self.config.name,
                    error=str(e), step=step,
                )
                return f"Error calling LLM: {e}"

            text = response.text

            await self.bus.emit(
                EventType.AGENT_STEP, source=self.config.name,
                step=step, response=text[:500],
            )

            # Check for final answer
            final_match = FINAL_ANSWER_RE.search(text)
            if final_match:
                answer = final_match.group(1).strip()
                await self.bus.emit(
                    EventType.AGENT_COMPLETED, source=self.config.name,
                    answer=answer[:500],
                )
                self.store.append_history(self.config.name, "assistant", answer)
                return answer

            # Check for code blocks to execute
            code_blocks = CODE_BLOCK_RE.findall(text)
            if code_blocks:
                history.append({"role": "assistant", "content": text})
                all_outputs = []
                for code in code_blocks:
                    result = execute(code, tool_callables)
                    output = result.output if result.success else f"Error: {result.error}"
                    if result.result is not None:
                        output += f"\nResult: {result.result}"
                    all_outputs.append(output)

                observation = "\n---\n".join(all_outputs)
                history.append({"role": "user", "content": f"Tool output:\n{observation}"})

                await self.bus.emit(
                    EventType.AGENT_STEP, source=self.config.name,
                    step=step, action="code_exec", observation=observation[:500],
                )
            else:
                # No code and no final answer - treat the whole response as the answer
                await self.bus.emit(
                    EventType.AGENT_COMPLETED, source=self.config.name,
                    answer=text[:500],
                )
                self.store.append_history(self.config.name, "assistant", text)
                return text

        await self.bus.emit(
            EventType.AGENT_ERROR, source=self.config.name,
            error="Max steps reached",
        )
        return "Max steps reached without a final answer."
