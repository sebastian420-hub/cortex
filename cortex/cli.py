"""Command-line interface for Cortex"""

import argparse
import asyncio
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Optional

from rich.panel import Panel
from rich.table import Table

from .agent import Cortex
from .cli_commands.commands import CommandContext, CommandRegistry
from .config import AgentConfig
from .core.feature_flags import FeatureManager
from .core.providers import ProviderError, ProviderFactory
from .hooks import HookManager
from .models import PermissionMode
from .output import OutputFormat
from .storage.history import get_history_file
from .storage.sessions import SessionManager
from .ui.console import console
from .ui.modes import UIMode, set_ui_mode
from .ui.repl import REPL

# Configure logging - only show WARNING and above by default
logging.basicConfig(level=logging.WARNING, format="%(levelname)s:%(name)s:%(message)s")

# Suppress noisy third-party loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("cortex.tools.registry").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

__version__ = "1.0.0"


def check_ollama() -> bool:
    """Check if Ollama is available"""
    try:
        import ollama

        ollama.list()
        return True
    except (ImportError, ConnectionError, Exception) as e:
        logger.debug(f"Ollama not available: {e}")
        return False


def list_providers():
    """List available providers and models"""
    table = Table(
        title="Available Providers and Models", show_header=True, header_style="bold cyan"
    )
    table.add_column("Provider", style="cyan")
    table.add_column("Model Name", style="green")
    table.add_column("Description", style="dim")
    table.add_column("API Key Required", style="yellow")

    # Ollama
    table.add_row(
        "Ollama", "llama3.2, deepseek-r1:8b, qwen2.5:32b, etc.", "Local models via Ollama", "No"
    )

    # DeepSeek
    deepseek_key = "Yes" if os.getenv("DEEPSEEK_API_KEY") else "[red]Yes (not set)[/red]"
    table.add_row(
        "DeepSeek",
        "deepseek-chat, deepseek-coder, deepseek-reasoner",
        "Cloud API - Best for coding, cheapest",
        deepseek_key,
    )

    # Anthropic
    anthropic_key = "Yes" if os.getenv("ANTHROPIC_API_KEY") else "[red]Yes (not set)[/red]"
    table.add_row(
        "Anthropic",
        "claude-3-5-sonnet-20241022, claude-3-haiku-20240307, claude-3-opus-20240229",
        "Cloud API - Claude models",
        anthropic_key,
    )

    # OpenRouter
    openrouter_key = "Yes" if os.getenv("OPENROUTER_API_KEY") else "[red]Yes (not set)[/red]"
    table.add_row(
        "OpenRouter",
        "devstral-2512, openrouter/* (any OpenRouter model)",
        "Cloud API - Access to multiple models via OpenRouter",
        openrouter_key,
    )

    console.print(table)
    console.print(
        "\n[dim]Note: Provider is auto-detected from model name. Use --provider to override.[/dim]"
    )


def validate_provider_setup(model: str, provider_override: Optional[str] = None) -> bool:
    """Validate that provider is properly set up"""
    try:
        provider = ProviderFactory.get_provider(model, provider_override)

        # Check API key for cloud providers
        if not provider.validate_api_key():
            provider_name = ProviderFactory.get_provider_name(model)
            if provider_name == "deepseek":
                console.print(
                    Panel(
                        "[red]Error:[/red] DEEPSEEK_API_KEY not set\n\n"
                        "Get your API key from: [cyan]https://platform.deepseek.com/[/cyan]\n\n"
                        "Set it with:\n"
                        "  [cyan]export DEEPSEEK_API_KEY=your_key_here[/cyan]",
                        title="API Key Required",
                        border_style="red",
                    )
                )
            elif provider_name == "anthropic":
                console.print(
                    Panel(
                        "[red]Error:[/red] ANTHROPIC_API_KEY not set\n\n"
                        "Get your API key from: [cyan]https://console.anthropic.com/[/cyan]\n\n"
                        "Set it with:\n"
                        "  [cyan]export ANTHROPIC_API_KEY=your_key_here[/cyan]",
                        title="API Key Required",
                        border_style="red",
                    )
                )
            return False

        # Check Ollama connection if using Ollama provider
        provider_name = ProviderFactory.get_provider_name(model)
        if provider_name == "ollama" and not check_ollama():
            console.print(
                Panel(
                    "[red]Error:[/red] Cannot connect to Ollama\n\n"
                    "Make sure Ollama is running:\n"
                    "  [cyan]ollama serve[/cyan]\n\n"
                    "And you have a model pulled:\n"
                    "  [cyan]ollama pull llama3.2[/cyan]",
                    title="Ollama Not Found",
                    border_style="red",
                )
            )
            return False

        return True
    except ProviderError as e:
        console.print(
            Panel(f"[red]Error:[/red] {str(e)}", title="Provider Error", border_style="red")
        )
        return False


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Cortex - A unified agent for coding, cybersecurity, and personal assistance",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  cortex                              # Start interactive session
  cortex --model llama3.3:70b         # Use different model
  cortex --auto-approve               # Skip permissions (dangerous!)
  cortex -p "your task"               # One-shot mode
  cortex --config config.yaml         # Use config file
  cortex --save-session mywork         # Save session
  cortex --load-session mywork        # Load session
  cortex -o json -p "list files"      # JSON output for scripting
  cortex --hooks-config hooks.yaml    # Custom hooks config
  cortex --no-hooks                   # Disable hook system
        """,
    )

    parser.add_argument("--version", action="version", version=f"Cortex {__version__}")

    parser.add_argument(
        "--model",
        "-m",
        default=None,
        help=(
            "Model to use (default: moonshotai/kimi-k2.5). "
            "Auto-detects provider from model name."
        ),
    )

    parser.add_argument(
        "--provider",
        choices=["ollama", "deepseek", "anthropic", "openrouter"],
        default=None,
        help="Override provider auto-detection (normally auto-detected from model name)",
    )

    parser.add_argument(
        "--list-providers", action="store_true", help="List available providers and models"
    )

    parser.add_argument(
        "--auto-approve", action="store_true", help="Auto-approve all actions (dangerous!)"
    )

    parser.add_argument("--plan-mode", action="store_true", help="Start in plan mode (read-only)")

    parser.add_argument(
        "--enhanced",
        action="store_true",
        help="Use enhanced agent with planning and layered memory",
    )

    parser.add_argument(
        "--routing",
        action="store_true",
        help="Enable intelligent model routing (auto-selects best model for task)",
    )

    parser.add_argument("--prompt", "-p", help="One-shot prompt (exit after completion)")

    parser.add_argument("--config", "-c", type=str, help="Path to configuration file (YAML)")

    parser.add_argument("--save-session", type=str, help="Save session with given name")

    parser.add_argument("--load-session", type=str, help="Load a saved session")

    parser.add_argument("--list-sessions", action="store_true", help="List all saved sessions")

    parser.add_argument(
        "--streaming", action="store_true", help="Use streaming responses (experimental)"
    )

    parser.add_argument(
        "--async",
        dest="use_async",
        action="store_true",
        help="Use async execution for non-blocking operation (experimental)",
    )

    parser.add_argument(
        "--project-dir",
        type=str,
        default=None,
        help="Project directory (default: current directory)",
    )

    parser.add_argument(
        "--output-format",
        "-o",
        choices=["text", "json", "stream-json"],
        default=None,
        help="Output format: text (default), json, or stream-json",
    )

    parser.add_argument("--no-hooks", action="store_true", help="Disable hook system")

    parser.add_argument(
        "--hooks-config", type=str, default=None, help="Path to hooks configuration file (YAML)"
    )

    parser.add_argument(
        "--ui-mode",
        choices=["minimal", "normal", "debug"],
        default=None,
        help=(
            "UI display mode: minimal (Claude Code style), "
            "normal (rich panels), debug (development details)"
        ),
    )

    args = parser.parse_args()

    # Handle list-providers command
    if args.list_providers:
        list_providers()
        sys.exit(0)

    # Load configuration - try default config/default.yaml first, then CLI arg
    config_path = None
    if args.config:
        config_path = Path(args.config)
    else:
        # Auto-load config/default.yaml if it exists
        default_config = Path(__file__).parent.parent / "config" / "default.yaml"
        if default_config.exists():
            config_path = default_config

    if config_path:
        config = AgentConfig.load(config_path)
        console.print(f"[dim]Loaded config from {config_path}[/dim]")
    else:
        config = AgentConfig()

    # Initialize FeatureManager with loaded config
    FeatureManager.get_instance(config.get_feature_flags_config())

    # Track if model was explicitly provided (for session loading logic)
    model_explicitly_provided = args.model is not None

    # Override with CLI arguments
    if args.model:
        config.model = args.model

    if args.provider:
        config.provider = args.provider

    # Enable intelligent routing if requested
    if args.routing:
        config.routing["enabled"] = True
        # Also ensure orchestration is enabled (new self-orchestrating system)
        if not hasattr(config, "orchestration"):
            config.orchestration = {}
        config.orchestration["enabled"] = True

        # Set default coordinator model if no model explicitly specified
        if not args.model:
            # Use full OpenRouter model name for API calls
            config.model = "xiaomi/mimo-v2-flash:free"
            config.provider = "openrouter"
            console.print(
                "[cyan]Model orchestration enabled - using "
                "xiaomi/mimo-v2-flash:free as coordinator[/cyan]"
            )
        else:
            console.print("[cyan]Model orchestration enabled (self-switching models)[/cyan]")

    # Validate provider setup
    if not validate_provider_setup(config.model, config.provider):
        sys.exit(1)

    # Determine permission mode
    if args.auto_approve:
        permission_mode = PermissionMode.AUTO_APPROVE
    elif args.plan_mode:
        permission_mode = PermissionMode.PLAN
    else:
        permission_mode = args.config and config.permission_mode or PermissionMode.NORMAL

    # Project directory
    project_dir = args.project_dir or os.getcwd()

    # Handle session management commands
    session_manager = SessionManager(Path.home() / ".cortex" / "sessions")

    if args.list_sessions:
        session_manager.show_sessions()
        sys.exit(0)

    # Run session cleanup on startup if enabled
    if config.session_retention.get("cleanup_on_startup", False):
        from .storage.cleanup import SessionCleanupManager

        cleanup_manager = SessionCleanupManager(
            sessions_dir=session_manager.sessions_dir,
            max_age_days=config.session_retention.get("max_age_days", 30),
            max_count=config.session_retention.get("max_count", 100),
            max_total_size_mb=config.session_retention.get("max_total_size_mb", 500),
        )
        stats = cleanup_manager.run_full_cleanup()
        if stats.sessions_removed > 0:
            console.print(
                f"[dim]Session cleanup: removed {stats.sessions_removed} old sessions, "
                f"freed {stats.bytes_freed // 1024} KB[/dim]"
            )

    # Determine output format
    output_format = OutputFormat.TEXT
    if args.output_format:
        output_format = OutputFormat(args.output_format)
    elif config.output_format:
        output_format = OutputFormat(config.output_format)

    # Set UI mode
    if args.ui_mode:
        ui_mode = UIMode(args.ui_mode)
        set_ui_mode(ui_mode)
        console.print(f"[dim]UI mode: {ui_mode.value}[/dim]")
    else:
        # Default to minimal mode (Claude Code style)
        set_ui_mode(UIMode.MINIMAL)

    # Set up hook manager
    hook_manager = HookManager()
    if not args.no_hooks and config.hooks_enabled:
        # Load hooks from config
        if config.hooks:
            hook_manager = HookManager.from_config({"hooks": config.hooks})

        # Load hooks from separate config file if specified
        if args.hooks_config:
            hooks_config_path = Path(args.hooks_config)
            if hooks_config_path.exists():
                try:
                    import yaml

                    with open(hooks_config_path) as f:
                        hooks_data = yaml.safe_load(f) or {}
                    hook_manager = HookManager.from_config(hooks_data)
                    console.print(f"[dim]Loaded hooks from {args.hooks_config}[/dim]")
                except Exception as e:
                    console.print(f"[yellow]Warning:[/yellow] Failed to load hooks config: {e}")
    elif args.no_hooks:
        hook_manager.disable()

    # Create unified agent
    is_enhanced = args.enhanced or (args.config and config.enable_planning)

    if is_enhanced:
        console.print("[cyan]Using enhanced features: planning and layered memory[/cyan]")

    agent = Cortex(
        model=config.model,
        project_dir=project_dir,
        permission_mode=permission_mode,
        config=config,
        hook_manager=hook_manager,
        output_format=output_format,
        enable_planning=is_enhanced,
        enable_layered_memory=is_enhanced,
    )

    # Load session if requested
    if args.load_session:
        session_data = session_manager.load_session(args.load_session)
        if session_data:
            # Load conversation history
            agent.conversation.history = session_data["conversation_history"]

            # Determine which model to use
            if model_explicitly_provided:
                # User explicitly provided --model, use it (switch model if different)
                target_model = config.model
                if target_model != agent.model:
                    try:
                        agent.switch_model(target_model, config.provider)
                    except ProviderError as e:
                        console.print(f"[red]Error switching model:[/red] {e}")
                        # Fall back to session's model if switch fails
                        session_model = session_data.get("model", agent.model)
                        if session_model != agent.model:
                            try:
                                agent.switch_model(session_model, config.provider)
                            except ProviderError:
                                # If both fail, keep current model (already initialized)
                                console.print(
                                    f"[yellow]Using current model:[/yellow] {agent.model}"
                                )
            else:
                # No --model provided, use session's saved model (backward compatible)
                session_model = session_data.get("model", agent.model)
                if session_model != agent.model:
                    try:
                        agent.switch_model(session_model, config.provider)
                    except ProviderError as e:
                        console.print(
                            f"[yellow]Warning:[/yellow] Could not switch to "
                            f"session's model ({session_model}): {e}"
                        )
                        console.print(
                            f"[yellow]Continuing with current model:[/yellow] {agent.model}"
                        )

            # Restore permission mode
            agent.permission_mode = session_data.get("permission_mode", agent.permission_mode)

    # Run
    if args.prompt:
        # One-shot mode
        console.print(Panel(f"[cyan]Task:[/cyan] {args.prompt}", title="One-shot Mode"))

        # Run in async mode if requested
        if args.use_async:
            asyncio.run(agent._process_message_async(args.prompt, use_streaming=args.streaming))
        else:
            agent._process_message(args.prompt, use_streaming=args.streaming)

        # Save session if requested
        if args.save_session:
            session_manager.save_session(
                args.save_session,
                agent.get_conversation_history(),
                str(agent.project_dir),
                agent.model,
                agent.permission_mode,
            )
    else:
        # Interactive mode
        run_interactive(
            agent, session_manager, use_streaming=args.streaming, use_async=args.use_async
        )


def run_interactive(
    agent: Cortex,
    session_manager: SessionManager,
    use_streaming: bool = False,
    use_async: bool = False,
):
    """Run interactive REPL session"""

    # Set up REPL
    history_file = get_history_file(Path.home())
    repl = REPL(str(history_file))

    # Initialize command registry
    command_registry = init_command_registry(session_manager)

    # Show banner
    repl.show_banner(
        project_name=agent.project_dir.name,
        model=agent.model,
        permission_mode=agent.permission_mode,
    )

    # Create callback for max iterations
    def on_max_iterations_reached(current: int, max_iter: int) -> Optional[int]:
        from rich.prompt import Confirm, IntPrompt

        console.print(
            f"\n[yellow]⚠️  Reached maximum iterations " f"({current}/{max_iter})[/yellow]"
        )

        if Confirm.ask("[cyan]Continue processing?[/cyan]", default=False):
            # Ask how many additional iterations
            additional = IntPrompt.ask(
                "[cyan]How many additional iterations?[/cyan]",
                default=agent.config.max_iterations_continue_amount,
            )
            return max(1, additional)  # Ensure at least 1
        return None  # Stop

    # Set callback on agent
    agent._on_max_iterations_reached = on_max_iterations_reached

    # Register signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        """Handle SIGINT and SIGTERM signals"""
        console.print("\n[yellow]Shutdown signal received. Cleaning up...[/yellow]")
        agent.request_shutdown()
        agent._cleanup()

        # Optionally save session if dirty
        if agent._session_dirty:
            try:
                from datetime import datetime

                auto_save_name = f"autosave_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                session_manager.save_session(
                    auto_save_name,
                    agent.get_conversation_history(),
                    str(agent.project_dir),
                    agent.model,
                    agent.permission_mode,
                )
                console.print(f"[dim]Session auto-saved as: {auto_save_name}[/dim]")
            except Exception as e:
                console.print(f"[yellow]Warning:[/yellow] Could not auto-save session: {e}")

        console.print("[cyan]👋 Goodbye![/cyan]")
        sys.exit(0)

    # Register handlers (Unix/Linux)
    # SIGINT is handled by KeyboardInterrupt catch block
    # if hasattr(signal, "SIGINT"):
    #     signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, signal_handler)

    # Main loop
    while True:
        try:
            # Check for shutdown request
            if agent._shutdown_requested:
                break

            # Get user input
            user_input = repl.prompt("\n> ")

            if not user_input.strip():
                continue

            # Handle commands
            if user_input.startswith("/"):
                handle_command(user_input, agent, session_manager, repl, command_registry)
                continue

            # Process with agent
            if use_async:
                # Async mode
                asyncio.run(agent._process_message_async(user_input, use_streaming=use_streaming))
            else:
                # Sync mode
                agent._process_message(user_input, use_streaming=use_streaming)

        except KeyboardInterrupt:
            # Handle Ctrl+C gracefully
            from rich.prompt import Confirm

            if Confirm.ask("\n[yellow]Exit Cortex?[/yellow]"):
                agent.request_shutdown()
                agent._cleanup()

                # Optionally save session if dirty
                if agent._session_dirty:
                    try:
                        from datetime import datetime

                        auto_save_name = f"autosave_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                        session_manager.save_session(
                            auto_save_name,
                            agent.get_conversation_history(),
                            str(agent.project_dir),
                            agent.model,
                            agent.permission_mode,
                        )
                        console.print(f"[dim]Session auto-saved as: {auto_save_name}[/dim]")
                    except Exception as e:
                        console.print(f"[yellow]Warning:[/yellow] Could not auto-save session: {e}")

                console.print("[cyan]👋 Goodbye![/cyan]")
                break
        except EOFError:
            # Handle EOF (Ctrl+D)
            agent.request_shutdown()
            agent._cleanup()
            break


def init_command_registry(session_manager: SessionManager) -> "CommandRegistry":
    """
    Initialize and populate the command registry.

    Args:
        session_manager: Session manager for session-related commands

    Returns:
        Populated CommandRegistry instance
    """
    from .cli_commands.commands import (
        CommandRegistry,
        # Basic commands
        ClearCommand,
        ResetContextCommand,
        HelpCommand,
        ExitCommand,
        # Mode commands
        PermissionModeCommand,
        UIModeCommand,
        PlanCommand,
        # Model commands
        ModelCommand,
        ProfileCommand,
        # Memory commands
        MemoryCommand,
        FocusCommand,
        ThinkingCommand,
        SummaryCommand,
        # Session commands
        SaveSessionCommand,
        LoadSessionCommand,
        ListSessionsCommand,
        SessionRecoveryCommand,
        # Stats commands
        ProjectCommand,
        StatsCommand,
        RoutingCommand,
        StorageCommand,
        CleanupCommand,
        # Transaction/Cache commands
        CacheCommand,
        RollbackCommand,
        TransactionsCommand,
    )

    registry = CommandRegistry()

    # Register basic commands
    registry.register(ClearCommand())
    registry.register(ResetContextCommand())
    registry.register(HelpCommand())
    registry.register(ExitCommand())

    # Register mode commands
    registry.register(PermissionModeCommand())
    registry.register(UIModeCommand())
    registry.register(PlanCommand())

    # Register model commands
    registry.register(ModelCommand())
    registry.register(ProfileCommand())

    # Register memory commands
    registry.register(MemoryCommand())
    registry.register(FocusCommand())
    registry.register(ThinkingCommand())
    registry.register(SummaryCommand())

    # Register session commands (need session_manager)
    registry.register(SaveSessionCommand(session_manager))
    registry.register(LoadSessionCommand(session_manager))
    registry.register(ListSessionsCommand(session_manager))
    registry.register(SessionRecoveryCommand())

    # Register stats commands
    registry.register(ProjectCommand())
    registry.register(StatsCommand())
    registry.register(RoutingCommand())
    registry.register(StorageCommand(session_manager))
    registry.register(CleanupCommand(session_manager))

    # Register transaction/cache commands
    registry.register(CacheCommand())
    registry.register(RollbackCommand())
    registry.register(TransactionsCommand())

    return registry


def handle_command(
    command: str,
    agent: Cortex,
    session_manager: SessionManager,
    repl: REPL,
    command_registry: Optional[CommandRegistry] = None,
):
    """Handle special commands"""

    logger = logging.getLogger(__name__)  # Initialize logger here
    logger.debug(f"Handling command: '{command}'")

    # Initialize registry if not provided
    if command_registry is None:
        command_registry = init_command_registry(session_manager)

    # Try using the command registry (new modular system)
    if command_registry:
        # Extract command name and args
        parts = command.split(maxsplit=1)
        cmd_name = parts[0][1:] if parts[0].startswith("/") else parts[0]  # Remove leading /
        cmd_args = parts[1] if len(parts) > 1 else None

        # Look up command in registry
        cmd_obj = command_registry.get(cmd_name)
        if cmd_obj:
            logger.debug(f"Using command registry for: {cmd_name}")
            try:
                # Create command context
                ctx = CommandContext(
                    agent=agent,
                    config=agent.config,
                    hook_manager=agent.hook_manager,
                    output_format=agent.output_format.value,
                    verbose=False,
                )
                # Execute command
                cmd_obj.execute(ctx, cmd_args)
                return
            except Exception as e:
                console.print(f"[red]Error executing command:[/red] {e}")
                logger.exception(f"Command execution failed: {cmd_name}")
                return

    # Unknown command - not in registry
    cmd_name = command.split()[0][1:] if command.startswith("/") else command.split()[0]
    logger.debug(f"Unknown command: '{cmd_name}'")
    console.print(f"[red]Unknown command: {command}[/red]")
    console.print("[dim]Type /help for available commands[/dim]")


if __name__ == "__main__":
    main()
