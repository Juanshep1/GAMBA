"""First-run interactive wizard using Rich prompts with auto-detection."""

from __future__ import annotations

import asyncio

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm, IntPrompt

from gamba.state.schemas import Config, ProviderConfig, InterfaceConfig, AgentConfig
from gamba.config import save_config, save_agent

console = Console()

AVAILABLE_TOOLS = [
    "web_search", "video_search", "file_read", "file_write", "file_list",
    "code_exec", "shell", "http_request", "delegate",
]


def _onboarding() -> None:
    """Ask the user about their goals to tailor the setup."""
    console.print("[bold]A few quick questions to set things up right:\n[/]")

    # Q1: Experience level
    console.print("  [bold]1.[/] How comfortable are you with AI agents?")
    console.print("     [1] New to this  [2] I've used ChatGPT/Claude  [3] I've built agents before")
    level = Prompt.ask("    ", choices=["1", "2", "3"], default="2")

    if level == "1":
        console.print("\n  [cyan]No worries! GAMBA will set up sensible defaults for you.[/]")
        console.print("  [dim]Your agents will work autonomously - just type what you need.[/]\n")
    elif level == "3":
        console.print("\n  [cyan]Nice. You'll have full control over agents, tools, and providers.[/]\n")

    # Q2: Primary use case
    console.print("  [bold]2.[/] What will you mainly use GAMBA for?")
    console.print("     [1] Research & information gathering")
    console.print("     [2] Coding & building things")
    console.print("     [3] Both research and coding")
    console.print("     [4] Something else")
    use_case = Prompt.ask("    ", choices=["1", "2", "3", "4"], default="3")
    console.print()

    # Q3: Privacy preference
    console.print("  [bold]3.[/] Privacy preference?")
    console.print("     [1] Cloud is fine (faster, more models)")
    console.print("     [2] Local only (private, no data leaves device)")
    console.print("     [3] Mix of both (local when possible, cloud as fallback)")
    privacy = Prompt.ask("    ", choices=["1", "2", "3"], default="3")
    console.print()

    # Q4: Device usage
    console.print("  [bold]4.[/] Where will you run GAMBA most?")
    console.print("     [1] This device only")
    console.print("     [2] Multiple devices (phone + laptop)")
    console.print("     [3] Server / always-on")
    device = Prompt.ask("    ", choices=["1", "2", "3"], default="1")
    console.print()

    # Summarize and store preferences
    use_labels = {"1": "research", "2": "coding", "3": "research + coding", "4": "general"}
    privacy_labels = {"1": "cloud", "2": "local-only", "3": "hybrid"}

    console.print(Panel.fit(
        f"  Use case: [cyan]{use_labels.get(use_case, 'general')}[/]\n"
        f"  Privacy: [cyan]{privacy_labels.get(privacy, 'hybrid')}[/]\n"
        f"  Multi-device: [cyan]{'yes' if device == '2' else 'no'}[/]",
        title="Got it",
        border_style="green",
    ))
    console.print()

    # Store for later steps
    _onboarding.use_case = use_case
    _onboarding.privacy = privacy
    _onboarding.level = level
    _onboarding.multi_device = device == "2"

# Default values
_onboarding.use_case = "3"
_onboarding.privacy = "3"
_onboarding.level = "2"
_onboarding.multi_device = False


def run_orientation() -> Config:
    """Run the first-time setup wizard. Returns the generated config."""
    console.print()
    console.print(Panel.fit(
        "[bold cyan]GAMBA[/] - Multi-Agent Framework\n"
        "[dim]Lightweight. Mobile-first. Sub-agent powered.[/]",
        border_style="cyan",
    ))
    console.print()

    # Onboarding questions - understand the user
    _onboarding()

    # Step 0: Auto-detect platform and local models
    config = Config()
    detection = _run_detection()

    # Step 1: AI Providers (with auto-detected local models)
    config = _setup_providers(config, detection)

    # Step 2: Interfaces
    config = _setup_interfaces(config)

    # Step 3: Sub-Agents
    _setup_agents(config)

    # Save config
    save_config(config)

    console.print()
    local_count = len(detection.get("local_models", [])) if detection else 0
    providers_str = ", ".join(config.providers.keys())
    console.print(Panel(
        f"[green]Configuration saved![/]\n\n"
        f"Platform: [cyan]{detection.get('platform_str', 'unknown') if detection else 'unknown'}[/]\n"
        f"Local models: [cyan]{local_count} detected[/]\n"
        f"Providers: [cyan]{providers_str}[/]\n"
        f"Interfaces: [cyan]{_enabled_interfaces(config)}[/]\n"
        f"Agents dir: [cyan]{config.agents_dir}[/]\n\n"
        f"Run [bold]python -m gamba[/] to start!",
        title="Setup Complete",
        border_style="green",
    ))

    return config


def _run_detection() -> dict:
    """Run auto-detection of platform and local models."""
    console.print("[bold]Scanning device...[/]\n")

    try:
        from gamba.core.detect import detect_all, detect_platform
        result = asyncio.run(detect_all())
    except Exception as e:
        console.print(f"[yellow]Detection error: {e}[/]\n")
        return {}

    plat = result.platform

    # Platform info
    platform_str = f"{plat.os}/{plat.device} ({plat.arch})"
    table = Table(title="Device Info", border_style="dim", show_header=False, pad_edge=False)
    table.add_column("Key", style="dim")
    table.add_column("Value", style="cyan")
    table.add_row("Platform", platform_str)
    table.add_row("Python", plat.python_version)
    if plat.ram_mb:
        table.add_row("RAM", f"{plat.ram_mb}MB")
    if plat.has_gpu:
        table.add_row("GPU", "Detected")
    if plat.storage_free_gb:
        table.add_row("Free Storage", f"{plat.storage_free_gb:.1f}GB")
    console.print(table)
    console.print()

    # Local models
    if result.local_models:
        model_table = Table(title="Local Models Found", border_style="green")
        model_table.add_column("Model", style="bold")
        model_table.add_column("Provider", style="cyan")
        model_table.add_column("Size", style="dim")
        model_table.add_column("Quantization", style="dim")
        for m in result.local_models:
            model_table.add_row(m.name, m.provider, m.size, m.quantization)
        console.print(model_table)
    else:
        console.print("[dim]No local models detected.[/]")
    console.print()

    # Recommendations
    if result.recommendations:
        for rec in result.recommendations:
            console.print(f"  [yellow]*[/] {rec}")
        console.print()

    return {
        "platform": result.platform,
        "platform_str": platform_str,
        "local_models": result.local_models,
        "local_providers": result.local_providers,
        "recommendations": result.recommendations,
    }


def _setup_providers(config: Config, detection: dict) -> Config:
    console.print("[bold]Step 1: AI Providers[/]\n")

    local_providers = detection.get("local_providers", [])
    local_models = detection.get("local_models", [])

    # Auto-add detected local providers
    if local_providers:
        for lp in local_providers:
            name = lp["name"]
            url = lp["url"]
            models = lp["models"]
            if Confirm.ask(f"Use detected [cyan]{name}[/] ({len(models)} models at {url})?", default=True):
                if name == "ollama":
                    default_model = models[0] if models else "llama3.2:3b"
                    config.providers["ollama"] = ProviderConfig(base_url=url, default_model=default_model)
                    if not config.default_provider or config.default_provider == "openrouter":
                        if Confirm.ask(f"Set [cyan]{name}[/] as default provider?", default=False):
                            config.default_provider = "ollama"
                elif name in ("lmstudio", "localai"):
                    # These are OpenAI-compatible, use as openrouter-like
                    default_model = models[0] if models else ""
                    config.providers[name] = ProviderConfig(base_url=url, default_model=default_model)

        console.print()

    # Cloud providers
    privacy = getattr(_onboarding, "privacy", "3")

    if privacy == "2" and local_providers:
        console.print("[dim]Privacy: local-only selected. Skipping cloud providers.[/]\n")
        if not config.default_provider and config.providers:
            config.default_provider = next(iter(config.providers))
        return config

    console.print("Cloud providers:")
    console.print("  [1] OpenRouter [dim](200+ models, pay-per-use)[/]")
    console.print("  [2] HuggingFace [dim](free tier available)[/]")
    console.print("  [3] Skip cloud [dim](local only)[/]")
    console.print()

    default_cloud = "3" if (privacy == "2" and local_providers) else "1"
    choice = Prompt.ask("Select cloud provider", choices=["1", "2", "3"], default=default_cloud)

    if choice == "1":
        api_key = Prompt.ask("OpenRouter API key")
        model = Prompt.ask("Default model", default="google/gemini-2.0-flash-001")
        config.providers["openrouter"] = ProviderConfig(api_key=api_key, default_model=model)
        if not config.default_provider or config.default_provider == "openrouter":
            config.default_provider = "openrouter"
    elif choice == "2":
        token = Prompt.ask("HuggingFace API token")
        model = Prompt.ask("Default model", default="meta-llama/Llama-3.1-8B-Instruct")
        config.providers["huggingface"] = ProviderConfig(api_token=token, default_model=model)
        if not config.default_provider:
            config.default_provider = "huggingface"
    elif choice == "3":
        if not config.providers:
            console.print("[red]No providers configured! You need at least one.[/]")
            return _setup_providers(config, detection)

    # Ensure default is set
    if not config.default_provider and config.providers:
        config.default_provider = next(iter(config.providers))

    console.print()
    return config


def _setup_interfaces(config: Config) -> Config:
    console.print("[bold]Step 2: Interfaces[/]\n")

    plat = detect_platform_quick()
    console.print("[dim]TUI (terminal dashboard) is always available.[/]")
    if plat == "termux":
        console.print("[dim]On Termux: Telegram bot recommended (lightweight, long-polling).[/]")
    console.print()

    config.interfaces["tui"] = InterfaceConfig(enabled=True)

    if Confirm.ask("Enable Telegram bot?", default=(plat == "termux")):
        token = Prompt.ask("Telegram bot token")
        config.interfaces["telegram"] = InterfaceConfig(enabled=True, bot_token=token)

    if Confirm.ask("Enable Discord bot?", default=False):
        token = Prompt.ask("Discord bot token")
        config.interfaces["discord"] = InterfaceConfig(enabled=True, bot_token=token)

    if Confirm.ask("Enable Web UI?", default=(plat != "termux")):
        port = IntPrompt.ask("Web UI port", default=8420)
        config.interfaces["web"] = InterfaceConfig(enabled=True, port=port)

    console.print()
    return config


def _setup_agents(config: Config) -> None:
    console.print("[bold]Step 3: Sub-Agents[/]\n")

    use_case = getattr(_onboarding, "use_case", "3")

    # Smart defaults based on onboarding
    if use_case == "1":
        default_agents = "researcher (web search + reports)"
    elif use_case == "2":
        default_agents = "coder (code + shell + files)"
    else:
        default_agents = "researcher + coder"

    console.print(f"  [dim]Based on your answers, recommended agents: [cyan]{default_agents}[/][/]\n")

    if Confirm.ask("Use recommended agents?", default=True):
        # Create tailored agents based on use case
        if use_case in ("1", "3"):
            save_agent(AgentConfig(
                name="researcher",
                description="Searches the web and synthesizes information into concise reports",
                tools=["web_search", "video_search", "http_request", "file_read", "file_write"],
                max_steps=15, temperature=0.3,
                system_prompt="You are a research agent. Search for current information and produce concise, sourced reports. Always use FINAL_ANSWER: to return your report.",
            ), config.agents_dir)
            console.print("  [green]Created: researcher[/]")

        if use_case in ("2", "3"):
            save_agent(AgentConfig(
                name="coder",
                description="Writes, reads, and executes code. Can create files and run shell commands.",
                tools=["code_exec", "file_read", "file_write", "file_list", "shell"],
                max_steps=20, temperature=0.2,
                system_prompt="You are a coding agent. Write clean, working code. Use code_exec to test, file_write to save, shell to run commands. Always use FINAL_ANSWER: to return your work.",
            ), config.agents_dir)
            console.print("  [green]Created: coder[/]")

        if use_case in ("1", "3"):
            save_agent(AgentConfig(
                name="analyst",
                description="Analyzes data, summarizes findings, and provides insights",
                tools=["web_search", "code_exec", "file_read", "file_write"],
                max_steps=15, temperature=0.4,
                system_prompt="You are an analysis agent. When given data or topics, analyze them thoroughly and provide structured insights. Use code_exec for calculations. Always use FINAL_ANSWER: to return your analysis.",
            ), config.agents_dir)
            console.print("  [green]Created: analyst[/]")

        console.print()

        if Confirm.ask("Add a custom agent too?", default=False):
            _create_custom_agent(config)
        return

    console.print("[dim]Define your sub-agents. You can add more later with /agent add[/]\n")

    _create_custom_agent(config)


def _create_custom_agent(config: Config) -> None:
    """Interactive custom agent creation loop."""
    while True:
        name = Prompt.ask("  Agent name")
        description = Prompt.ask("  What does this agent do?")

        console.print(f"\n  Available tools: [dim]{', '.join(AVAILABLE_TOOLS)}[/]")
        tools_str = Prompt.ask("  Tools (comma-separated)", default="web_search, file_read")
        tools = [t.strip() for t in tools_str.split(",") if t.strip()]

        agent = AgentConfig(
            name=name,
            description=description,
            tools=tools,
        )
        save_agent(agent, config.agents_dir)
        console.print(f"  [green]Created: {name}[/]\n")

        if not Confirm.ask("  Create another agent?", default=False):
            break


def detect_platform_quick() -> str:
    """Quick platform check without async."""
    import os
    if os.environ.get("TERMUX_VERSION") or os.path.exists("/data/data/com.termux"):
        return "termux"
    if os.environ.get("ASHELL") or os.path.exists("/var/mobile"):
        return "ios"
    return "desktop"


def _enabled_interfaces(config: Config) -> str:
    enabled = [name for name, iface in config.interfaces.items() if iface.enabled]
    return ", ".join(enabled) if enabled else "tui"
