"""Async pub/sub message bus - the nervous system of GAMBA."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine


class EventType(str, Enum):
    # Agent lifecycle
    AGENT_SPAWNED = "agent.spawned"
    AGENT_STEP = "agent.step"
    AGENT_MESSAGE = "agent.message"
    AGENT_COMPLETED = "agent.completed"
    AGENT_ERROR = "agent.error"
    # Orchestrator
    ORCHESTRATOR_PLAN = "orchestrator.plan"
    ORCHESTRATOR_RESPONSE = "orchestrator.response"
    # User
    USER_INPUT = "user.input"
    # System
    SYSTEM_LOG = "system.log"


@dataclass
class Event:
    type: EventType
    data: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = "system"


Handler = Callable[[Event], Coroutine[Any, Any, None]]


class MessageBus:
    """In-process async pub/sub. All real-time visibility flows through here."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Handler]] = {}
        self._global_subscribers: list[Handler] = []

    def subscribe(self, event_type: str | EventType, handler: Handler) -> Callable[[], None]:
        key = str(event_type)
        self._subscribers.setdefault(key, []).append(handler)
        return lambda: self._subscribers[key].remove(handler)

    def subscribe_all(self, handler: Handler) -> Callable[[], None]:
        self._global_subscribers.append(handler)
        return lambda: self._global_subscribers.remove(handler)

    async def publish(self, event: Event) -> None:
        key = str(event.type)
        handlers = self._subscribers.get(key, []) + self._global_subscribers
        tasks = [asyncio.create_task(h(event)) for h in handlers]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def emit(self, event_type: EventType, source: str = "system", **data: Any) -> None:
        await self.publish(Event(type=event_type, data=data, source=source))
