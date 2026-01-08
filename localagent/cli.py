"""Command-line interface for LocalAgent"""

import sys
import os
import argparse
from pathlib import Path

import ollama
from rich.console import Console
from rich.panel import Panel

from .agent import LocalAgent
from .models import PermissionMode
from .config import AgentConfig
from .ui.console import console
from .ui.repl import REPL
from .storage.history import get_history_file
from .storage.sessions import SessionManager

__version__ = "1.0.0"


def check_ollama() -> bool:
    """Check if Ollama is available"""
    try:
        ollama.list()
        return True
    except:
        return False


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="LocalAgent - Autonomous coding assistant with local models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  localagent                          # Start interactive session
  localagent --model llama3.3:70b      # Use different model
  localagent --auto-approve            # Skip permissions (dangerous!)
  localagent -p "your task"            # One-shot mode
  localagent --config config.yaml      # Use config file
  localagent --save-session mywork     # Save session
  localagent --load-session mywork    # Load session
        """
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version=f"LocalAgent {__version__}"
    )
    
    parser.add_argument(
        "--model", "-m",
        default=None,
        help="Ollama model to use (default: llama3.2)"
    )
    
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Auto-approve all actions (dangerous!)"
    )
    
    parser.add_argument(
        "--plan-mode",
        action="store_true",
        help="Start in plan mode (read-only)"
    )
    
    parser.add_argument(
        "--prompt", "-p",
        help="One-shot prompt (exit after completion)"
    )
    
    parser.add_argument(
        "--config", "-c",
        type=str,
        help="Path to configuration file (YAML)"
    )
    
    parser.add_argument(
        "--save-session",
        type=str,
        help="Save session with given name"
    )
    
    parser.add_argument(
        "--load-session",
        type=str,
        help="Load a saved session"
    )
    
    parser.add_argument(
        "--list-sessions",
        action="store_true",
        help="List all saved sessions"
    )
    
    parser.add_argument(
        "--streaming",
        action="store_true",
        help="Use streaming responses (experimental)"
    )
    
    parser.add_argument(
        "--project-dir",
        type=str,
        default=None,
        help="Project directory (default: current directory)"
    )
    
    args = parser.parse_args()
    
    # Check Ollama connection
    if not check_ollama():
        console.print(Panel(
            "[red]Error:[/red] Cannot connect to Ollama\n\n"
            "Make sure Ollama is running:\n"
            "  [cyan]ollama serve[/cyan]\n\n"
            "And you have a model pulled:\n"
            "  [cyan]ollama pull llama3.2[/cyan]",
            title="Ollama Not Found",
            border_style="red"
        ))
        sys.exit(1)
    
    # Load configuration
    config = AgentConfig()
    if args.config:
        config_path = Path(args.config)
        if config_path.exists():
            config = AgentConfig.load(config_path)
        else:
            console.print(f"[yellow]Warning:[/yellow] Config file not found: {args.config}")
    
    # Override with CLI arguments
    if args.model:
        config.model = args.model
    
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
    session_manager = SessionManager(Path.home() / ".localagent" / "sessions")
    
    if args.list_sessions:
        session_manager.show_sessions()
        sys.exit(0)
    
    # Create agent
    agent = LocalAgent(
        model=config.model,
        project_dir=project_dir,
        permission_mode=permission_mode,
        config=config
    )
    
    # Load session if requested
    if args.load_session:
        session_data = session_manager.load_session(args.load_session)
        if session_data:
            agent.conversation.history = session_data["conversation_history"]
            agent.model = session_data.get("model", agent.model)
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
                agent.permission_mode
            )
    else:
        # Interactive mode
        run_interactive(agent, session_manager, use_streaming=args.streaming)


def run_interactive(
    agent: LocalAgent,
    session_manager: SessionManager,
    use_streaming: bool = False
):
    """Run interactive REPL session"""
    
    # Set up REPL
    history_file = get_history_file(Path.home())
    repl = REPL(str(history_file))
    
    # Show banner
    repl.show_banner(
        project_name=agent.project_dir.name,
        model=agent.model,
        permission_mode=agent.permission_mode
    )
    
    # Main loop
    while True:
        try:
            # Get user input
            user_input = repl.prompt("\n> ")
            
            if not user_input.strip():
                continue
            
            # Handle commands
            if user_input.startswith('/'):
                handle_command(user_input, agent, session_manager, repl)
                continue
            
            # Process with agent
            agent._process_message(user_input, use_streaming=use_streaming)
            
        except KeyboardInterrupt:
            from rich.prompt import Confirm
            if Confirm.ask("\n[yellow]Exit LocalAgent?[/yellow]"):
                console.print("[cyan]👋 Goodbye![/cyan]")
                break
        except EOFError:
            break


def handle_command(
    command: str,
    agent: LocalAgent,
    session_manager: SessionManager,
    repl: REPL
):
    """Handle special commands"""
    from datetime import datetime
    
    cmd = command.lower().strip()
    
    if cmd == '/help':
        repl.show_help()
    
    elif cmd == '/clear':
        agent.clear_conversation()
        console.print("[green]✓[/green] Conversation cleared")
    
    elif cmd.startswith('/mode'):
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
    
    elif cmd == '/project':
        info = f"""
[bold]Project Information[/bold]
Path: {agent.project_dir}
Mode: {agent.permission_mode}
Model: {agent.model}
Session: {(datetime.now() - agent.session_start).seconds // 60} minutes
Tokens: {agent.conversation.get_token_count()}
"""
        console.print(Panel(info, title="Project"))
    
    elif cmd.startswith('/save'):
        parts = cmd.split()
        session_name = parts[1] if len(parts) > 1 else f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        session_manager.save_session(
            session_name,
            agent.get_conversation_history(),
            str(agent.project_dir),
            agent.model,
            agent.permission_mode
        )
    
    elif cmd.startswith('/load'):
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
    
    elif cmd == '/sessions':
        session_manager.show_sessions()
    
    elif cmd == '/exit':
        raise KeyboardInterrupt
    
    else:
        console.print(f"[red]Unknown command: {command}[/red]")
        console.print("[dim]Type /help for available commands[/dim]")


if __name__ == "__main__":
    main()

