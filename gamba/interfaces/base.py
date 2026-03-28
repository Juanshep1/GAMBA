"""Abstract interface - all UIs implement this contract."""

from __future__ import annotations

from abc import ABC, abstractmethod

from gamba.core.message_bus import MessageBus, EventType, Event
from gamba.state.schemas import Config


class BaseInterface(ABC):
    """All interfaces subscribe to bus events and forward user input."""

    def __init__(self, bus: MessageBus, config: Config) -> None:
        self.bus = bus
        self.config = config
        bus.subscribe(EventType.ORCHESTRATOR_RESPONSE, self.on_response)
        bus.subscribe(EventType.AGENT_STEP, self.on_agent_step)
        bus.subscribe(EventType.AGENT_MESSAGE, self.on_agent_message)

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def on_response(self, event: Event) -> None: ...

    @abstractmethod
    async def on_agent_step(self, event: Event) -> None: ...

    @abstractmethod
    async def on_agent_message(self, event: Event) -> None: ...

    async def send_user_input(self, text: str, source: str = "unknown") -> None:
        await self.bus.emit(EventType.USER_INPUT, source=source, message=text)
