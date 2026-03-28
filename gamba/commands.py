"""Slash commands for configuring and controlling GAMBA at runtime."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm, IntPrompt

from gamba.config import load_config, save_config, load_agents, save_agent
from gamba.state.schemas import Config, ProviderConfig, InterfaceConfig, AgentConfig

if TYPE_CHECKING:
    from gamba.core.orchestrator import Orchestrator
    from gamba.core.message_bus import MessageBus

console = Console()

AVAILABLE_TOOLS = [
    "web_search", "video_search", "file_read", "file_write", "file_list",
    "code_exec", "shell", "http_request", "delegate",
]

HELP_TEXT = """
[bold cyan]GAMBA Commands[/]

[bold]/help[/]                  Show this help
[bold]/status[/]                Show current config, agents, and providers
[bold]/agents[/]                List all configured agents
[bold]/agent add[/]             Create a new sub-agent
[bold]/agent remove <name>[/]   Remove a sub-agent
[bold]/agent edit <name>[/]     Edit a sub-agent's config
[bold]/agent info <name>[/]     Show agent details
[bold]/provider[/]              List configured providers
[bold]/provider add[/]          Add a new AI provider
[bold]/provider remove <name>[/] Remove a provider
[bold]/provider default <name>[/] Set default provider
[bold]/model[/]                 Show current default model
[bold]/model set <model>[/]     Change default model
[bold]/scan[/]                  Scan for local AI models
[bold]/interface[/]             List enabled interfaces
[bold]/interface enable <name>[/]  Enable an interface (telegram/discord/web)
[bold]/interface disable <name>[/] Disable an interface
[bold]/key <provider> <key>[/]  Set API key for a provider
[bold]/config[/]                Show raw config
[bold]/clear[/]                 Clear the activity log
[bold]/reset[/]                 Re-run the orientation wizard
[bold]/quit[/]                  Exit GAMBA
"""


def is_command(text: str) -> bool:
    return text.strip().startswith("/")


async def handle_command(
    text: str,
    config: Config,
    orchestrator: "Orchestrator | None" = None,
    bus: "MessageBus | None" = None,
) -> str:
    """Process a slash command. Returns the response string."""
    parts = text.strip().split(None, 2)
    cmd = parts[0].lower()
    arg1 = parts[1] if len(parts) > 1 else ""
    arg2 = parts[2] if len(parts) > 2 else ""

    try:
        if cmd == "/help":
            return HELP_TEXT

        elif cmd == "/status":
            return _cmd_status(config, orchestrator)

        elif cmd == "/agents":
            return _cmd_agents(config)

        elif cmd == "/agent":
            return _cmd_agent(config, arg1, arg2, orchestrator)

        elif cmd == "/provider":
            return _cmd_provider(config, arg1, arg2)

        elif cmd == "/model":
            return _cmd_model(config, arg1, arg2)

        elif cmd == "/scan":
            return await _cmd_scan()

        elif cmd == "/interface":
            return _cmd_interface(config, arg1, arg2)

        elif cmd == "/key":
            return _cmd_key(config, arg1, arg2)

        elif cmd == "/config":
            return _cmd_show_config(config)

        elif cmd == "/clear":
            return "__CLEAR__"

        elif cmd == "/reset":
            return _cmd_reset()

        elif cmd in ("/quit", "/exit", "/q"):
            return "__QUIT__"

        else:
            return f"[yellow]Unknown command: {cmd}[/]\nType [bold]/help[/] for available commands."

    except Exception as e:
        return f"[red]Error: {e}[/]"


def _cmd_status(config: Config, orchestrator: "Orchestrator | None") -> str:
    lines = []
    lines.append("[bold cyan]GAMBA Status[/]\n")

    # Provider
    default = config.default_provider
    providers = list(config.providers.keys())
    lines.append(f"  Default provider: [cyan]{default}[/]")
    lines.append(f"  All providers: [dim]{', '.join(providers) or 'none'}[/]")

    # Model
    pconfig = config.providers.get(default)
    if pconfig:
        lines.append(f"  Default model: [cyan]{pconfig.default_model or 'provider default'}[/]")

    # Agents
    agents = load_agents(config.agents_dir)
    lines.append(f"\n  Agents: [cyan]{len(agents)}[/]")
    for a in agents:
        status = ""
        if orchestrator and a.name in orchestrator.agents:
            status = " [green](loaded)[/]"
        lines.append(f"    - {a.name}: {a.description[:50]}{status}")

    # Interfaces
    enabled = [n for n, i in config.interfaces.items() if i.enabled]
    lines.append(f"\n  Interfaces: [cyan]{', '.join(enabled) or 'none'}[/]")

    return "\n".join(lines)


def _cmd_agents(config: Config) -> str:
    agents = load_agents(config.agents_dir)
    if not agents:
        return "[dim]No agents configured. Use [bold]/agent add[/] to create one.[/]"

    table_lines = ["[bold cyan]Configured Agents[/]\n"]
    for a in agents:
        tools = ", ".join(a.tools[:4])
        if len(a.tools) > 4:
            tools += f" +{len(a.tools) - 4} more"
        provider = a.provider or "(default)"
        table_lines.append(f"  [bold]{a.name}[/]")
        table_lines.append(f"    {a.description}")
        table_lines.append(f"    Tools: [dim]{tools}[/]  Provider: [dim]{provider}[/]  Steps: [dim]{a.max_steps}[/]")
        table_lines.append("")

    return "\n".join(table_lines)


def _cmd_agent(config: Config, action: str, rest: str, orchestrator: "Orchestrator | None") -> str:
    if not action or action == "list":
        return _cmd_agents(config)

    elif action == "add":
        return _cmd_agent_add_interactive(config)

    elif action == "remove":
        name = rest.strip()
        if not name:
            return "[yellow]Usage: /agent remove <name>[/]"
        path = Path(config.agents_dir) / f"{name}.yaml"
        if not path.exists():
            return f"[yellow]Agent '{name}' not found[/]"
        path.unlink()
        return f"[green]Removed agent: {name}[/]\nRestart GAMBA to apply changes."

    elif action == "info":
        name = rest.strip()
        if not name:
            return "[yellow]Usage: /agent info <name>[/]"
        agents = load_agents(config.agents_dir)
        agent = next((a for a in agents if a.name == name), None)
        if not agent:
            return f"[yellow]Agent '{name}' not found[/]"
        lines = [f"[bold cyan]{agent.name}[/]\n"]
        lines.append(f"  Description: {agent.description}")
        lines.append(f"  Provider: {agent.provider or '(default)'}")
        lines.append(f"  Model: {agent.model or '(provider default)'}")
        lines.append(f"  Tools: {', '.join(agent.tools)}")
        lines.append(f"  Max steps: {agent.max_steps}")
        lines.append(f"  Temperature: {agent.temperature}")
        lines.append(f"  Autonomy: {agent.autonomy}")
        if agent.system_prompt:
            lines.append(f"  System prompt: [dim]{agent.system_prompt[:100]}...[/]")
        return "\n".join(lines)

    elif action == "edit":
        name = rest.strip()
        if not name:
            return "[yellow]Usage: /agent edit <name>[/]"
        return _cmd_agent_edit_interactive(config, name)

    else:
        return "[yellow]Usage: /agent [add|remove|edit|info|list] [name][/]"


def _cmd_agent_add_interactive(config: Config) -> str:
    """Interactive agent creation."""
    try:
        name = Prompt.ask("  Agent name")
        description = Prompt.ask("  What does this agent do?")

        console.print(f"\n  Available tools: [dim]{', '.join(AVAILABLE_TOOLS)}[/]")
        tools_str = Prompt.ask("  Tools (comma-separated)", default="web_search, file_read")
        tools = [t.strip() for t in tools_str.split(",") if t.strip()]

        model = Prompt.ask("  Model override (Enter for default)", default="")
        temp = Prompt.ask("  Temperature", default="0.5")
        max_steps = IntPrompt.ask("  Max steps", default=15)

        system_prompt = ""
        if Confirm.ask("  Add custom system prompt?", default=False):
            system_prompt = Prompt.ask("  System prompt")

        agent = AgentConfig(
            name=name,
            description=description,
            tools=tools,
            model=model,
            temperature=float(temp),
            max_steps=max_steps,
            system_prompt=system_prompt,
        )
        save_agent(agent, config.agents_dir)
        return f"\n[green]Created agent: {name}[/]\nRestart GAMBA to load it, or it'll be available next session."
    except (KeyboardInterrupt, EOFError):
        return "\n[dim]Cancelled[/]"


def _cmd_agent_edit_interactive(config: Config, name: str) -> str:
    """Interactive agent editing."""
    agents = load_agents(config.agents_dir)
    agent = next((a for a in agents if a.name == name), None)
    if not agent:
        return f"[yellow]Agent '{name}' not found[/]"

    try:
        console.print(f"\n  Editing [bold]{name}[/] (press Enter to keep current value)\n")

        desc = Prompt.ask("  Description", default=agent.description)
        tools_str = Prompt.ask("  Tools", default=", ".join(agent.tools))
        tools = [t.strip() for t in tools_str.split(",") if t.strip()]
        model = Prompt.ask("  Model", default=agent.model or "")
        temp = Prompt.ask("  Temperature", default=str(agent.temperature))
        max_steps = IntPrompt.ask("  Max steps", default=agent.max_steps)

        updated = AgentConfig(
            name=name,
            description=desc,
            tools=tools,
            model=model,
            temperature=float(temp),
            max_steps=max_steps,
            system_prompt=agent.system_prompt,
            autonomy=agent.autonomy,
        )
        save_agent(updated, config.agents_dir)
        return f"\n[green]Updated agent: {name}[/]\nRestart GAMBA to apply changes."
    except (KeyboardInterrupt, EOFError):
        return "\n[dim]Cancelled[/]"


def _cmd_provider(config: Config, action: str, rest: str) -> str:
    if not action or action == "list":
        if not config.providers:
            return "[dim]No providers configured. Use [bold]/provider add[/].[/]"
        lines = ["[bold cyan]Providers[/]\n"]
        for name, p in config.providers.items():
            default_tag = " [green](default)[/]" if name == config.default_provider else ""
            key_status = ""
            if p.api_key:
                key_status = f"  Key: [dim]{p.api_key[:12]}...[/]"
            elif p.api_token:
                key_status = f"  Token: [dim]{p.api_token[:12]}...[/]"
            elif p.base_url:
                key_status = f"  URL: [dim]{p.base_url}[/]"
            lines.append(f"  [bold]{name}[/]{default_tag}")
            lines.append(f"    Model: [dim]{p.default_model or 'default'}[/]{key_status}")
        return "\n".join(lines)

    elif action == "add":
        return _cmd_provider_add_interactive(config)

    elif action == "remove":
        name = rest.strip()
        if not name:
            return "[yellow]Usage: /provider remove <name>[/]"
        if name not in config.providers:
            return f"[yellow]Provider '{name}' not found[/]"
        del config.providers[name]
        if config.default_provider == name:
            config.default_provider = next(iter(config.providers), "")
        save_config(config)
        return f"[green]Removed provider: {name}[/]"

    elif action == "default":
        name = rest.strip()
        if not name:
            return "[yellow]Usage: /provider default <name>[/]"
        if name not in config.providers:
            return f"[yellow]Provider '{name}' not configured[/]"
        config.default_provider = name
        save_config(config)
        return f"[green]Default provider set to: {name}[/]"

    else:
        return "[yellow]Usage: /provider [add|remove|default|list] [name][/]"


def _cmd_provider_add_interactive(config: Config) -> str:
    try:
        console.print("\n  [1] OpenRouter  [2] HuggingFace  [3] Ollama")
        choice = Prompt.ask("  Select", choices=["1", "2", "3"])

        if choice == "1":
            key = Prompt.ask("  OpenRouter API key")
            model = Prompt.ask("  Default model", default="google/gemini-2.0-flash-001")
            config.providers["openrouter"] = ProviderConfig(api_key=key, default_model=model)
            name = "openrouter"
        elif choice == "2":
            token = Prompt.ask("  HuggingFace token")
            model = Prompt.ask("  Default model", default="meta-llama/Llama-3.1-8B-Instruct")
            config.providers["huggingface"] = ProviderConfig(api_token=token, default_model=model)
            name = "huggingface"
        elif choice == "3":
            url = Prompt.ask("  Ollama URL", default="http://localhost:11434")
            model = Prompt.ask("  Default model", default="llama3.2:3b")
            config.providers["ollama"] = ProviderConfig(base_url=url, default_model=model)
            name = "ollama"

        if not config.default_provider:
            config.default_provider = name

        save_config(config)
        return f"\n[green]Added provider: {name}[/]"
    except (KeyboardInterrupt, EOFError):
        return "\n[dim]Cancelled[/]"


def _cmd_model(config: Config, action: str, rest: str) -> str:
    pconfig = config.providers.get(config.default_provider)
    if not pconfig:
        return "[yellow]No default provider configured[/]"

    if not action:
        return f"Current model: [cyan]{pconfig.default_model or 'provider default'}[/] (provider: {config.default_provider})"

    elif action == "set":
        model = rest.strip()
        if not model:
            return "[yellow]Usage: /model set <model-name>[/]"
        pconfig.default_model = model
        save_config(config)
        return f"[green]Default model set to: {model}[/]"

    else:
        # Treat the whole thing as model name
        model = f"{action} {rest}".strip()
        pconfig.default_model = model
        save_config(config)
        return f"[green]Default model set to: {model}[/]"


async def _cmd_scan() -> str:
    from gamba.core.detect import detect_all

    result = await detect_all()
    p = result.platform

    lines = [f"[bold cyan]Device Scan[/]\n"]
    lines.append(f"  Platform: [cyan]{p.os}/{p.device} ({p.arch})[/]")
    lines.append(f"  Python: {p.python_version}")
    if p.ram_mb:
        lines.append(f"  RAM: {p.ram_mb}MB")
    if p.has_gpu:
        lines.append(f"  GPU: [green]Detected[/]")
    if p.storage_free_gb:
        lines.append(f"  Storage: {p.storage_free_gb:.1f}GB free")

    if result.local_models:
        lines.append(f"\n  [bold]Local Models ({len(result.local_models)}):[/]")
        for m in result.local_models:
            lines.append(f"    - {m.name} [dim][{m.provider}] {m.size} {m.quantization}[/]")
    else:
        lines.append("\n  [dim]No local models found[/]")

    if result.recommendations:
        lines.append("")
        for r in result.recommendations:
            lines.append(f"  [yellow]*[/] {r}")

    return "\n".join(lines)


def _cmd_interface(config: Config, action: str, rest: str) -> str:
    if not action or action == "list":
        lines = ["[bold cyan]Interfaces[/]\n"]
        for name, iface in config.interfaces.items():
            status = "[green]enabled[/]" if iface.enabled else "[dim]disabled[/]"
            extra = ""
            if iface.bot_token:
                extra = f"  token: [dim]{iface.bot_token[:10]}...[/]"
            if name == "web" and iface.enabled:
                extra = f"  port: [dim]{iface.port}[/]"
            lines.append(f"  {name}: {status}{extra}")
        return "\n".join(lines)

    elif action == "enable":
        name = rest.strip()
        if not name:
            return "[yellow]Usage: /interface enable <telegram|discord|web>[/]"
        if name not in config.interfaces:
            config.interfaces[name] = InterfaceConfig()
        iface = config.interfaces[name]

        if name in ("telegram", "discord") and not iface.bot_token:
            try:
                token = Prompt.ask(f"  {name.title()} bot token")
                iface.bot_token = token
            except (KeyboardInterrupt, EOFError):
                return "\n[dim]Cancelled[/]"

        if name == "web" and not iface.port:
            iface.port = 8420

        iface.enabled = True
        save_config(config)
        return f"[green]Enabled: {name}[/]\nRestart GAMBA to activate."

    elif action == "disable":
        name = rest.strip()
        if not name:
            return "[yellow]Usage: /interface disable <name>[/]"
        if name in config.interfaces:
            config.interfaces[name].enabled = False
            save_config(config)
        return f"[dim]Disabled: {name}[/]"

    else:
        return "[yellow]Usage: /interface [enable|disable|list] [name][/]"


def _cmd_key(config: Config, provider: str, key: str) -> str:
    if not provider or not key:
        return "[yellow]Usage: /key <provider> <api-key>[/]\nExample: /key openrouter sk-or-..."

    if provider not in config.providers:
        config.providers[provider] = ProviderConfig()

    pconfig = config.providers[provider]
    if provider == "huggingface":
        pconfig.api_token = key.strip()
    else:
        pconfig.api_key = key.strip()

    if not config.default_provider:
        config.default_provider = provider

    save_config(config)
    return f"[green]API key updated for: {provider}[/]"


def _cmd_show_config(config: Config) -> str:
    import yaml
    data = config.model_dump()
    # Mask keys
    for pname, pdata in data.get("providers", {}).items():
        if pdata.get("api_key"):
            pdata["api_key"] = pdata["api_key"][:12] + "..."
        if pdata.get("api_token"):
            pdata["api_token"] = pdata["api_token"][:12] + "..."
        if pdata.get("bot_token"):
            pdata["bot_token"] = pdata["bot_token"][:12] + "..."
    for iname, idata in data.get("interfaces", {}).items():
        if idata.get("bot_token"):
            idata["bot_token"] = idata["bot_token"][:12] + "..."
    return f"[dim]{yaml.dump(data, default_flow_style=False, sort_keys=False)}[/]"


def _cmd_reset() -> str:
    from gamba.orientation import run_orientation
    try:
        run_orientation()
        return "[green]Configuration updated![/]\nRestart GAMBA to apply all changes."
    except (KeyboardInterrupt, EOFError):
        return "\n[dim]Cancelled[/]"
