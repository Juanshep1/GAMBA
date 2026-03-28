"""Textual TUI App - 3-panel dashboard for GAMBA."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

try:
    from textual.app import App, ComposeResult
    from textual.containers import Horizontal, Vertical
    from textual.widgets import Header, Footer, RichLog, Input, Static, Label
    from textual.binding import Binding
    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False

if TYPE_CHECKING:
    from gamba.core.message_bus import MessageBus, Event
    from gamba.core.orchestrator import Orchestrator
    from gamba.state.schemas import Config


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


if HAS_TEXTUAL:
    class AgentListPanel(Static):
        """Left sidebar showing agent names and status."""

        def __init__(self, agents: dict) -> None:
            super().__init__()
            self.agents = agents
            self.statuses: dict[str, str] = {name: "idle" for name in agents}

        def compose(self) -> ComposeResult:
            yield Label("[bold cyan]AGENTS[/]")
            yield Label("")  # spacer
            for name in self.agents:
                yield Label(f"  {name} [dim][idle][/]", id=f"agent-{name}")
            yield Label("")
            yield Label(f"[dim]{len(self.agents)} configured[/]")

        def update_status(self, agent_name: str, status: str) -> None:
            if agent_name not in self.statuses:
                return
            self.statuses[agent_name] = status
            colors = {"idle": "dim", "running": "bold green", "error": "bold red", "done": "bold cyan"}
            color = colors.get(status, "dim")
            try:
                label = self.query_one(f"#agent-{agent_name}", Label)
                indicator = {"idle": " ", "running": ">", "error": "!", "done": "*"}.get(status, " ")
                label.update(f"  {indicator} {agent_name} [{color}][{status}][/]")
            except Exception:
                pass

    class StatusBar(Static):
        """Bottom status bar showing connection state."""

        DEFAULT_CSS = """
        StatusBar {
            dock: bottom;
            height: 1;
            background: $surface-darken-2;
            padding: 0 1;
            color: $text-muted;
        }
        """

        def __init__(self, agent_count: int) -> None:
            super().__init__()
            self.agent_count = agent_count

        def compose(self) -> ComposeResult:
            yield Label(
                f"[dim]GAMBA v0.1 | {self.agent_count} agents | Ctrl+Q quit | Ctrl+L clear[/]"
            )

    class GambaApp(App):
        """Main TUI application."""

        TITLE = "GAMBA"
        CSS_PATH = "styles.tcss"
        BINDINGS = [
            Binding("ctrl+q", "quit", "Quit"),
            Binding("ctrl+l", "clear_log", "Clear"),
        ]

        def __init__(self, bus: "MessageBus", config: "Config", orchestrator: "Orchestrator") -> None:
            super().__init__()
            self.bus = bus
            self.gamba_config = config
            self.orchestrator = orchestrator

        def compose(self) -> ComposeResult:
            yield Header(show_clock=True)
            with Horizontal():
                yield AgentListPanel(self.orchestrator.agents)
                with Vertical(id="main-area"):
                    yield RichLog(id="activity", highlight=True, markup=True, wrap=True)
                    yield Input(placeholder="Type a message... (Enter to send)", id="chat-input")
            yield StatusBar(len(self.orchestrator.agents))

        async def on_mount(self) -> None:
            from gamba.core.message_bus import EventType

            log = self.query_one("#activity", RichLog)
            log.write(f"[bold cyan]GAMBA[/] ready. [{_ts()}]")
            agents = ", ".join(self.orchestrator.agents.keys()) or "none"
            log.write(f"[dim]Agents: {agents}[/]")
            log.write(f"[dim]Type /help for commands[/]")
            log.write("")

            self.bus.subscribe(EventType.ORCHESTRATOR_RESPONSE, self._on_response)
            self.bus.subscribe(EventType.AGENT_STEP, self._on_step)
            self.bus.subscribe(EventType.AGENT_MESSAGE, self._on_message)
            self.bus.subscribe(EventType.AGENT_SPAWNED, self._on_spawned)
            self.bus.subscribe(EventType.AGENT_COMPLETED, self._on_completed)
            self.bus.subscribe(EventType.AGENT_ERROR, self._on_error)
            self.bus.subscribe(EventType.ORCHESTRATOR_PLAN, self._on_plan)
            self.bus.subscribe(EventType.SYSTEM_LOG, self._on_system_log)

            # Focus the input
            self.query_one("#chat-input", Input).focus()

        async def on_input_submitted(self, event: Input.Submitted) -> None:
            from gamba.core.message_bus import EventType
            from gamba.commands import is_command, handle_command
            from gamba.config import load_config

            text = event.value.strip()
            if not text:
                return
            event.input.clear()
            log = self.query_one("#activity", RichLog)

            # Handle slash commands
            if is_command(text):
                log.write(f"[{_ts()}] [bold]>[/] {text}")
                active_config = load_config()
                result = await handle_command(text, active_config, self.orchestrator, self.bus)
                if result == "__QUIT__":
                    self.exit()
                elif result == "__CLEAR__":
                    log.clear()
                    log.write(f"[bold cyan]GAMBA[/] log cleared. [{_ts()}]")
                else:
                    log.write(result)
                    log.write("")
                return

            log.write(f"[{_ts()}] [bold]You:[/] {text}")
            await self.bus.emit(EventType.USER_INPUT, source="tui", message=text)

        async def _on_response(self, event: "Event") -> None:
            response = event.data.get("response", "")
            log = self.query_one("#activity", RichLog)
            log.write("")
            log.write(f"[{_ts()}] [bold green]GAMBA:[/] {response}")
            log.write("")

        async def _on_step(self, event: "Event") -> None:
            log = self.query_one("#activity", RichLog)
            source = event.source
            step = event.data.get("step", "")
            action = event.data.get("action", "")
            observation = event.data.get("observation", "")
            panel = self.query_one(AgentListPanel)
            panel.update_status(source, "running")
            if action:
                log.write(f"  [dim][{_ts()}] [{source}] {action}[/]")
                if observation:
                    for line in observation.split("\n")[:3]:
                        log.write(f"  [dim]    {line[:100]}[/]")
            else:
                preview = event.data.get("response", "")[:100]
                log.write(f"  [dim][{_ts()}] [{source}] step {step}: {preview}[/]")

        async def _on_message(self, event: "Event") -> None:
            log = self.query_one("#activity", RichLog)
            target = event.data.get("target", "")
            msg = event.data.get("message", "")
            log.write(f"  [{_ts()}] [cyan]{event.source} -> {target}:[/] {msg[:100]}")

        async def _on_spawned(self, event: "Event") -> None:
            log = self.query_one("#activity", RichLog)
            task = event.data.get("task", "")
            log.write(f"  [{_ts()}] [green][ {event.source} ] Started:[/] {task[:80]}")
            panel = self.query_one(AgentListPanel)
            panel.update_status(event.source, "running")

        async def _on_completed(self, event: "Event") -> None:
            log = self.query_one("#activity", RichLog)
            answer = event.data.get("answer", "")
            log.write(f"  [{_ts()}] [green][ {event.source} ] Done:[/] {answer[:80]}")
            panel = self.query_one(AgentListPanel)
            panel.update_status(event.source, "done")

        async def _on_error(self, event: "Event") -> None:
            log = self.query_one("#activity", RichLog)
            error = event.data.get("error", "")
            log.write(f"  [{_ts()}] [bold red][ {event.source} ] Error:[/] {error}")
            panel = self.query_one(AgentListPanel)
            panel.update_status(event.source, "error")

        async def _on_plan(self, event: "Event") -> None:
            log = self.query_one("#activity", RichLog)
            plan = event.data.get("plan", [])
            for agent_name, task in plan:
                log.write(f"  [{_ts()}] [yellow]>>> {agent_name}:[/] {task[:80]}")

        async def _on_system_log(self, event: "Event") -> None:
            log = self.query_one("#activity", RichLog)
            msg = event.data.get("message", "")
            log.write(f"  [dim][{_ts()}] {msg}[/]")

        def action_clear_log(self) -> None:
            log = self.query_one("#activity", RichLog)
            log.clear()
            log.write(f"[bold cyan]GAMBA[/] log cleared. [{_ts()}]")
