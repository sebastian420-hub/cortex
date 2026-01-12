"""Command-line interface for Cortex"""

import sys
import os
import argparse
import signal
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Confirm

from .agent import Cortex
from .models import PermissionMode
from .config import AgentConfig
from .core.providers import ProviderFactory, ProviderError
from .ui.console import console
from .ui.repl import REPL
from .storage.history import get_history_file
from .storage.sessions import SessionManager
from .output import OutputFormat
from .hooks import HookManager

__version__ = "1.0.0"


def check_ollama() -> bool:
    """Check if Ollama is available"""
    try:
        import ollama

        ollama.list()
        return True
    except:
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
        help="Model to use (default: llama3.2). Auto-detects provider from model name.",
    )

    parser.add_argument(
        "--provider",
        choices=["ollama", "deepseek", "anthropic"],
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

    parser.add_argument("--prompt", "-p", help="One-shot prompt (exit after completion)")

    parser.add_argument("--config", "-c", type=str, help="Path to configuration file (YAML)")

    parser.add_argument("--save-session", type=str, help="Save session with given name")

    parser.add_argument("--load-session", type=str, help="Load a saved session")

    parser.add_argument("--list-sessions", action="store_true", help="List all saved sessions")

    parser.add_argument(
        "--streaming", action="store_true", help="Use streaming responses (experimental)"
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

    # Track if model was explicitly provided (for session loading logic)
    model_explicitly_provided = args.model is not None

    # Override with CLI arguments
    if args.model:
        config.model = args.model

    if args.provider:
        config.provider = args.provider

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

    # Create agent
    agent = Cortex(
        model=config.model,
        project_dir=project_dir,
        permission_mode=permission_mode,
        config=config,
        hook_manager=hook_manager,
        output_format=output_format,
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
                            f"[yellow]Warning:[/yellow] Could not switch to session's model ({session_model}): {e}"
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
        run_interactive(agent, session_manager, use_streaming=args.streaming)


def run_interactive(agent: Cortex, session_manager: SessionManager, use_streaming: bool = False):
    """Run interactive REPL session"""

    # Set up REPL
    history_file = get_history_file(Path.home())
    repl = REPL(str(history_file))

    # Show banner
    repl.show_banner(
        project_name=agent.project_dir.name,
        model=agent.model,
        permission_mode=agent.permission_mode,
    )

    # Create callback for max iterations
    def on_max_iterations_reached(current: int, max_iter: int) -> Optional[int]:
        from rich.prompt import Confirm, IntPrompt

        console.print(f"\n[yellow]⚠️  Reached maximum iterations ({current}/{max_iter})[/yellow]")

        if Confirm.ask("[cyan]Continue processing?[/cyan]", default=False):
            additional = IntPrompt.ask(
                f"[cyan]How many additional iterations?[/cyan]",
                default=agent.config.max_iterations_continue_amount,
            )
            return max(1, additional)
        return None

    agent._on_max_iterations_reached = on_max_iterations_reached

    # Main loop
    while not agent._shutdown_requested:
        try:
            user_input = repl.prompt("\n> ")

            if user_input is None:
                # Handle Ctrl+D (EOF)
                raise EOFError

            if not user_input.strip():
                continue

            if user_input.startswith("/"):
                # Gracefully exit on /exit command
                if user_input.lower().strip() == '/exit':
                    raise EOFError
                handle_command(user_input, agent, session_manager, repl)
                continue

            # This is where the agent processes the message.
            # We wrap it in a try/except to catch the user's interrupt.
            try:
                agent._process_message(user_input, use_streaming=use_streaming)
            except KeyboardInterrupt:
                agent.request_shutdown()  # Tell the agent loop to stop
                console.print("\n[bold red]Task interrupted.[/bold red] Returning to prompt.")
            finally:
                # Ensure the shutdown request is cleared so the agent can be used again.
                agent.clear_shutdown_request()

        except (EOFError, KeyboardInterrupt):
            # Handle Ctrl+D or /exit to gracefully exit the application
            if Confirm.ask("\n[yellow]Exit Cortex?[/yellow]"):
                agent.request_shutdown()
                agent._cleanup()
                console.print("\n[cyan]👋 Goodbye![/cyan]")
                break
            else:
                continue


def handle_command(command: str, agent: Cortex, session_manager: SessionManager, repl: REPL):
    """Handle special commands"""
    from datetime import datetime

    cmd = command.lower().strip()

    if cmd.startswith("/help"):
        from .help import HelpSystem

        help_system = HelpSystem(project_dir=agent.project_dir, console=console)
        # Extract arguments after /help
        args = command[5:].strip() if len(command) > 5 else ""
        help_system.handle_help_command(args)

    elif cmd == "/clear":
        agent.clear_conversation()
        console.print("[green]✓[/green] Conversation cleared")

    elif cmd.startswith("/mode"):
        parts = cmd.split()
        if len(parts) > 1:
            mode = parts[1]
            if mode in [PermissionMode.NORMAL, PermissionMode.AUTO_APPROVE, PermissionMode.PLAN]:
                agent.permission_mode = mode
                # Update system prompt
                agent.conversation.history[0]["content"] = agent._get_system_prompt()
                console.print(f"[green]✓[/green] Mode changed to: {mode}")
            else:
                console.print("[red]Invalid mode. Use: normal, auto, or plan[/red]")
        else:
            console.print(f"Current mode: {agent.permission_mode}")

    elif cmd == "/project":
        info = f"""
[bold]Project Information[/bold]
Path: {agent.project_dir}
Mode: {agent.permission_mode}
Model: {agent.model}
Session: {(datetime.now() - agent.session_start).seconds // 60} minutes
Tokens: {agent.conversation.get_token_count()}
"""
        console.print(Panel(info, title="Project"))

    elif cmd.startswith("/save"):
        parts = cmd.split()
        session_name = (
            parts[1] if len(parts) > 1 else f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        session_manager.save_session(
            session_name,
            agent.get_conversation_history(),
            str(agent.project_dir),
            agent.model,
            agent.permission_mode,
        )

    elif cmd.startswith("/load"):
        parts = cmd.split()
        if len(parts) > 1:
            session_name = parts[1]
            session_data = session_manager.load_session(session_name)
            if session_data:
                agent.conversation.history = session_data["conversation_history"]
                agent.model = session_data.get("model", agent.model)
                agent.permission_mode = session_data.get("permission_mode", agent.permission_mode)
                console.print("[green]✓[/green] Session loaded")
        else:
            console.print("[red]Usage: /load <session_name>[/red]")

    elif cmd == "/sessions":
        session_manager.show_sessions()

    elif cmd == "/storage":
        # Show storage statistics
        from .storage.cleanup import SessionCleanupManager

        cleanup_manager = SessionCleanupManager(
            sessions_dir=session_manager.sessions_dir,
            max_age_days=agent.config.session_retention.get("max_age_days", 30),
            max_count=agent.config.session_retention.get("max_count", 100),
            max_total_size_mb=agent.config.session_retention.get("max_total_size_mb", 500),
        )
        stats = cleanup_manager.get_storage_stats()
        info = f"""
[bold]Storage Statistics[/bold]
Sessions: {stats['session_count']} / {stats['limit_count']} ({stats['usage_percent_count']}%)
Size: {stats['total_size_mb']} MB / {stats['limit_size_mb']} MB ({stats['usage_percent_size']}%)
Max Age: {stats['limit_age_days']} days

Oldest: {stats['oldest_session'] or 'N/A'}
Newest: {stats['newest_session'] or 'N/A'}
"""
        console.print(Panel(info, title="Storage"))

    elif cmd == "/cleanup":
        # Manual cleanup
        from .storage.cleanup import SessionCleanupManager

        cleanup_manager = SessionCleanupManager(
            sessions_dir=session_manager.sessions_dir,
            max_age_days=agent.config.session_retention.get("max_age_days", 30),
            max_count=agent.config.session_retention.get("max_count", 100),
            max_total_size_mb=agent.config.session_retention.get("max_total_size_mb", 500),
        )
        stats = cleanup_manager.run_full_cleanup()
        if stats.sessions_removed > 0:
            console.print(
                f"[green]✓[/green] Removed {stats.sessions_removed} sessions, "
                f"freed {stats.bytes_freed // 1024} KB"
            )
        else:
            console.print("[green]✓[/green] No sessions needed cleanup")
        if stats.errors:
            for error in stats.errors:
                console.print(f"[red]Error:[/red] {error}")

    elif cmd == "/exit":
        raise KeyboardInterrupt

    elif cmd.startswith("/cache"):
        # Cache management command
        from .cache import get_file_cache, clear_cache

        parts = cmd.split()
        cache = get_file_cache(agent.config.get_file_cache_config())

        if len(parts) > 1 and parts[1] == "clear":
            clear_cache()
            console.print("[green]✓[/green] File cache cleared")
        else:
            # Show cache stats
            stats = cache.get_stats()
            info = f"""
[bold]File Cache Statistics[/bold]
Enabled: {stats['enabled']}
Entries: {stats['entries']} / {stats['max_entries']}
Size: {stats['size_mb']:.2f} MB / {stats['max_size_mb']:.2f} MB
Hit Rate: {stats['hit_rate']*100:.1f}% ({stats['hits']} hits, {stats['misses']} misses)
"""
            console.print(Panel(info, title="Cache"))

    elif cmd == "/rollback":
        # Rollback active transaction
        from .core.transaction import get_transaction_manager

        tm = get_transaction_manager(agent.config.get_transactions_config())

        if tm.has_active_transaction():
            tx = tm.get_current_transaction()
            files = tx.get_files_modified()
            if tm.rollback():
                console.print(f"[green]✓[/green] Rolled back {len(files)} file(s)")
                for f in files:
                    console.print(f"  [dim]- {f}[/dim]")
            else:
                console.print("[red]Error:[/red] Rollback failed")
        else:
            console.print("[yellow]No active transaction to rollback[/yellow]")
            # Show last transaction info
            last_tx = tm.get_last_transaction()
            if last_tx:
                console.print(f"[dim]Last transaction: {last_tx.id} ({last_tx.state.value})[/dim]")

    elif cmd == "/transactions":
        # Show transaction statistics
        from .core.transaction import get_transaction_manager

        tm = get_transaction_manager(agent.config.get_transactions_config())
        stats = tm.get_stats()
        info = f"""
[bold]Transaction Statistics[/bold]
Enabled: {stats['enabled']}
Active Transaction: {stats['active_transaction'] or 'None'}
History: {stats['history_count']} / {stats['max_backups']}
Committed: {stats['committed']}
Rolled Back: {stats['rolled_back']}
Backup Dir: {stats['backup_dir']}
"""
        console.print(Panel(info, title="Transactions"))

    # Phase 4: New slash commands
    elif cmd == "/summary":
        # Show conversation summary
        from .core.summarization import SimpleSummarizer

        summarizer = SimpleSummarizer()
        history = agent.get_conversation_history()
        if len(history) > 1:  # More than just system prompt
            summary = summarizer.summarize(history[1:])  # Skip system prompt
            summary_msg = summary.to_message()
            console.print(
                Panel(
                    summary_msg.get("content", "No summary available"),
                    title="[bold]Conversation Summary[/bold]",
                    border_style="cyan",
                )
            )
        else:
            console.print("[dim]No conversation to summarize yet.[/dim]")

    elif cmd == "/plan":
        # Enter planning mode
        agent.permission_mode = PermissionMode.PLAN
        agent.conversation.history[0]["content"] = agent._get_system_prompt()
        console.print("[cyan]📋 Entered PLAN mode (read-only)[/cyan]")
        console.print("[dim]Use /mode normal to return to normal mode[/dim]")

    elif cmd.startswith("/reset-context"):
        # Clear conversation but preserve memory bank
        memory_backup = agent.memory_bank.to_dict() if agent.memory_bank else None
        agent.clear_conversation()
        if memory_backup:
            from .core.memory import MemoryBank

            agent.memory_bank = MemoryBank.from_dict(memory_backup)
            # Re-inject memory into system prompt
            agent.conversation.history[0]["content"] = agent._get_system_prompt()
        console.print("[green]✓[/green] Context cleared. Memory preserved.")
        console.print(
            f"[dim]Memory items: {len(agent.memory_bank.items) if agent.memory_bank else 0}[/dim]"
        )

    elif cmd.startswith("/focus"):
        # Focus on a specific directory
        parts = command.split(maxsplit=1)
        if len(parts) > 1:
            from pathlib import Path
            from .core.memory import MemorySource

            focus_path = Path(parts[1]).resolve()
            if focus_path.exists() and focus_path.is_dir():
                # Add to memory as a fact
                agent.memory_bank.add_fact(
                    f"User focused on directory: {focus_path}", source=MemorySource.USER
                )
                console.print(f"[green]✓[/green] Focus set to: {focus_path}")
                console.print("[dim]Future searches will prioritize this directory[/dim]")
            else:
                console.print(f"[red]Directory not found: {parts[1]}[/red]")
        else:
            console.print("[dim]Usage: /focus <directory_path>[/dim]")

    elif cmd.startswith("/thinking"):
        # Toggle thinking display
        parts = cmd.split()
        if len(parts) > 1:
            toggle = parts[1].lower()
            if toggle == "on":
                agent.show_thinking = True
                console.print("[green]✓[/green] Thinking display enabled")
            elif toggle == "off":
                agent.show_thinking = False
                console.print("[green]✓[/green] Thinking display disabled")
            else:
                console.print("[red]Usage: /thinking [on|off][/red]")
        else:
            agent.show_thinking = not agent.show_thinking
            status = "enabled" if agent.show_thinking else "disabled"
            console.print(f"[green]✓[/green] Thinking display {status}")

    elif cmd == "/memory":
        # Show memory bank contents
        if agent.memory_bank and agent.memory_bank.items:
            console.print(
                Panel(
                    agent.memory_bank.get_full_display(),
                    title="[bold]Memory Bank[/bold]",
                    border_style="yellow",
                )
            )
        else:
            console.print("[dim]Memory bank is empty.[/dim]")

    elif cmd == "/stats":
        # Show session statistics
        history = agent.get_conversation_history()
        truncation_stats = agent.conversation.get_truncation_stats()
        loop_stats = agent.loop_guard.get_stats()

        stats_text = f"""
[bold]Session Statistics[/bold]

Messages: {len(history)}
Tokens: {agent.conversation.get_token_count()}
Tools Used: {len(set(agent._tools_used))} unique / {len(agent._tools_used)} total

[bold]Context Management[/bold]
Truncations: {truncation_stats.get('truncation_count', 0)}
Summarizations: {truncation_stats.get('summarization_count', 0)}
Messages Removed: {truncation_stats.get('total_messages_removed', 0)}

[bold]Loop Guard[/bold]
Iterations: {loop_stats.get('current_iteration', 0)}
Unique Operations: {loop_stats.get('unique_operations_count', 0)}
Files Read: {loop_stats.get('files_read_count', 0)}
Files Written: {loop_stats.get('files_written_count', 0)}

[bold]Memory Bank[/bold]
Items: {len(agent.memory_bank.items) if agent.memory_bank else 0}
"""
        console.print(Panel(stats_text, title="Stats", border_style="cyan"))

    else:
        console.print(f"[red]Unknown command: {command}[/red]")
        console.print("[dim]Type /help for available commands[/dim]")


if __name__ == "__main__":
    main()
