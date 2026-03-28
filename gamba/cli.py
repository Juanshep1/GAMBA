"""CLI entry point - argument parsing and startup."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="gamba",
        description="GAMBA - Lightweight multi-agent framework",
    )
    parser.add_argument("prompt", nargs="?", help="One-shot prompt (skip TUI)")
    parser.add_argument("--setup", action="store_true", help="Run orientation wizard")
    parser.add_argument("--config", default="./data/config.yaml", help="Config file path")
    parser.add_argument("--no-tui", action="store_true", help="Disable TUI, use simple console")
    args = parser.parse_args()

    # Change to project directory if running from elsewhere
    project_dir = Path(__file__).parent.parent
    if not Path("./data").exists() and (project_dir / "data").exists():
        import os
        os.chdir(project_dir)

    # Run setup if requested or no config exists
    if args.setup or not Path(args.config).exists():
        from gamba.orientation import run_orientation
        run_orientation()
        if args.setup:
            return

    # Load config
    from gamba.config import load_config
    config = load_config(args.config)

    if args.prompt:
        # One-shot mode
        asyncio.run(_oneshot(config, args.prompt))
    else:
        # Interactive mode
        asyncio.run(_interactive(config, args.no_tui))


async def _oneshot(config: "Config", prompt: str) -> None:
    """Run a single prompt and exit."""
    from rich.console import Console
    from rich.panel import Panel
    from gamba.core.message_bus import MessageBus, EventType
    from gamba.core.orchestrator import Orchestrator

    console = Console()
    bus = MessageBus()
    orchestrator = Orchestrator(config, bus)

    response_received = asyncio.Event()
    response_text = ""

    async def on_response(event):
        nonlocal response_text
        response_text = event.data.get("response", "")
        response_received.set()

    async def on_plan(event):
        plan = event.data.get("plan", [])
        agents = ", ".join(f"[bold]{a}[/]" for a, _ in plan)
        console.print(f"  [yellow]>>> Delegating to: {agents}[/]")

    async def on_spawned(event):
        task = event.data.get("task", "")
        console.print(f"  [green][ {event.source} ][/] Started: {task[:80]}")

    async def on_step(event):
        source = event.source
        step = event.data.get("step", "")
        action = event.data.get("action", "")
        if action:
            console.print(f"  [dim][ {source} ] {action}[/]")
        else:
            preview = event.data.get("response", "")[:100]
            console.print(f"  [dim][ {source} ] step {step}: {preview}[/]")

    async def on_message(event):
        target = event.data.get("target", "")
        msg = event.data.get("message", "")
        console.print(f"  [cyan][ {event.source} -> {target} ][/] {msg[:80]}")

    async def on_completed(event):
        console.print(f"  [green][ {event.source} ] Done[/]")

    async def on_error(event):
        error = event.data.get("error", "")
        console.print(f"  [red][ {event.source} ] Error: {error}[/]")

    bus.subscribe(EventType.ORCHESTRATOR_RESPONSE, on_response)
    bus.subscribe(EventType.ORCHESTRATOR_PLAN, on_plan)
    bus.subscribe(EventType.AGENT_SPAWNED, on_spawned)
    bus.subscribe(EventType.AGENT_STEP, on_step)
    bus.subscribe(EventType.AGENT_MESSAGE, on_message)
    bus.subscribe(EventType.AGENT_COMPLETED, on_completed)
    bus.subscribe(EventType.AGENT_ERROR, on_error)

    console.print(f"[bold cyan]GAMBA[/] processing: {prompt}\n")

    await bus.emit(EventType.USER_INPUT, source="cli", message=prompt)

    try:
        await asyncio.wait_for(response_received.wait(), timeout=120)
    except asyncio.TimeoutError:
        console.print("[yellow]Timed out waiting for response.[/]")

    if response_text:
        console.print()
        console.print(Panel(response_text, title="[bold cyan]GAMBA[/]", border_style="cyan", expand=False))
    else:
        console.print("[yellow]No response received.[/]")

    await orchestrator.shutdown()


async def _interactive(config: "Config", no_tui: bool) -> None:
    """Run interactive mode with TUI or simple console, plus enabled interfaces."""
    from gamba.core.message_bus import MessageBus, EventType
    from gamba.core.orchestrator import Orchestrator

    bus = MessageBus()
    orchestrator = Orchestrator(config, bus)

    background_tasks = []

    # Start Telegram bot if enabled
    telegram_cfg = config.interfaces.get("telegram")
    if telegram_cfg and telegram_cfg.enabled:
        try:
            from gamba.interfaces.telegram_bot import TelegramBot
            bot = TelegramBot(bus, config)
            background_tasks.append(asyncio.create_task(bot.start()))
        except (ImportError, ValueError) as e:
            from rich.console import Console
            Console().print(f"[yellow]Telegram: {e}[/]")

    # Start Discord bot if enabled
    discord_cfg = config.interfaces.get("discord")
    if discord_cfg and discord_cfg.enabled:
        try:
            from gamba.interfaces.discord_bot import DiscordBot
            bot = DiscordBot(bus, config)
            background_tasks.append(asyncio.create_task(bot.start()))
        except (ImportError, ValueError) as e:
            from rich.console import Console
            Console().print(f"[yellow]Discord: {e}[/]")

    # Start Web server if enabled
    web_cfg = config.interfaces.get("web")
    if web_cfg and web_cfg.enabled:
        try:
            from gamba.interfaces.web.server import WebServer
            server = WebServer(bus, config)
            background_tasks.append(asyncio.create_task(server.start()))
        except (ImportError, ValueError) as e:
            from rich.console import Console
            Console().print(f"[yellow]Web: {e}[/]")

    # Main interface: TUI or simple console
    tui_enabled = config.interfaces.get("tui", None)
    if not no_tui and tui_enabled and tui_enabled.enabled:
        try:
            from gamba.interfaces.tui.app import GambaApp
            app = GambaApp(bus, config, orchestrator)
            await app.run_async()
        except ImportError:
            no_tui = True

    if no_tui:
        await _simple_console(bus, orchestrator)

    # Cancel background tasks
    for task in background_tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    await orchestrator.shutdown()


async def _simple_console(bus: "MessageBus", orchestrator: "Orchestrator") -> None:
    """Fallback simple console interface with rich real-time visibility."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from gamba.core.message_bus import EventType

    console = Console()
    console.print(Panel.fit(
        "[bold cyan]GAMBA[/] - Console Mode\n"
        f"[dim]Agents: {', '.join(orchestrator.agents.keys()) or 'none (direct mode)'}[/]\n"
        "[dim]Type /help for commands, /quit to exit[/]",
        border_style="cyan",
    ))
    console.print()

    from gamba.commands import is_command, handle_command
    from gamba.config import load_config
    active_config = load_config()

    response_received = asyncio.Event()
    last_response = ""

    async def on_response(event):
        nonlocal last_response
        last_response = event.data.get("response", "")
        response_received.set()

    async def on_plan(event):
        plan = event.data.get("plan", [])
        agents = ", ".join(f"[bold]{a}[/]" for a, _ in plan)
        console.print(f"  [yellow]>>> Delegating to: {agents}[/]")

    async def on_spawned(event):
        task = event.data.get("task", "")
        console.print(f"  [green][ {event.source} ][/] Started: {task[:80]}")

    async def on_step(event):
        source = event.source
        step = event.data.get("step", "")
        action = event.data.get("action", "")
        observation = event.data.get("observation", "")
        if action:
            console.print(f"  [dim][ {source} ] {action}[/]")
            if observation:
                for line in observation.split("\n")[:5]:
                    console.print(f"  [dim]    {line}[/]")
        else:
            preview = event.data.get("response", "")[:100]
            console.print(f"  [dim][ {source} ] step {step}: {preview}[/]")

    async def on_message(event):
        target = event.data.get("target", "")
        msg = event.data.get("message", "")
        console.print(f"  [cyan][ {event.source} -> {target} ][/] {msg[:100]}")

    async def on_completed(event):
        answer = event.data.get("answer", "")
        console.print(f"  [green][ {event.source} ] Done[/] ({len(answer)} chars)")

    async def on_error(event):
        error = event.data.get("error", "")
        console.print(f"  [red][ {event.source} ] Error: {error}[/]")

    bus.subscribe(EventType.ORCHESTRATOR_RESPONSE, on_response)
    bus.subscribe(EventType.ORCHESTRATOR_PLAN, on_plan)
    bus.subscribe(EventType.AGENT_SPAWNED, on_spawned)
    bus.subscribe(EventType.AGENT_STEP, on_step)
    bus.subscribe(EventType.AGENT_MESSAGE, on_message)
    bus.subscribe(EventType.AGENT_COMPLETED, on_completed)
    bus.subscribe(EventType.AGENT_ERROR, on_error)

    while True:
        try:
            prompt = await asyncio.get_event_loop().run_in_executor(
                None, lambda: console.input("[bold cyan]>[/] ")
            )
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye![/]")
            break

        if prompt.strip().lower() in ("quit", "exit", "q"):
            console.print("[dim]Goodbye![/]")
            break

        if not prompt.strip():
            continue

        # Handle slash commands
        if is_command(prompt):
            result = await handle_command(prompt, active_config, orchestrator, bus)
            if result == "__QUIT__":
                console.print("[dim]Goodbye![/]")
                break
            elif result == "__CLEAR__":
                console.clear()
            else:
                console.print(result)
                console.print()
            continue

        response_received.clear()
        last_response = ""
        await bus.emit(EventType.USER_INPUT, source="console", message=prompt)

        try:
            await asyncio.wait_for(response_received.wait(), timeout=120)
        except asyncio.TimeoutError:
            console.print("[yellow]Timed out waiting for response.[/]")
            continue

        if last_response:
            console.print()
            console.print(Panel(last_response, title="[bold cyan]GAMBA[/]", border_style="cyan", expand=False))
            console.print()


if __name__ == "__main__":
    main()
