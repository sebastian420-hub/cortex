#!/usr/bin/env python3
"""
LocalAgent - A Claude Code-like terminal agent using local models

Installation:
    pip install ollama rich prompt_toolkit

Usage:
    python localagent.py                    # Start interactive session
    python localagent.py --model llama3.3   # Use different model
    python localagent.py --auto-approve     # Skip permissions (dangerous!)
    python localagent.py -p "your task"     # One-shot mode

Author: Your implementation of autonomous coding agent
"""

import sys
import os
import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
import argparse

try:
    import ollama
    from rich.console import Console
    from rich.panel import Panel
    from rich.syntax import Syntax
    from rich.markdown import Markdown
    from rich.prompt import Confirm, Prompt
    from rich.table import Table
    from rich.live import Live
    from rich.spinner import Spinner
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("\nInstall with: pip install ollama rich prompt_toolkit")
    sys.exit(1)

console = Console()

# Tool definitions matching Anthropic's function calling format
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file. Use this to understand existing code before making changes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the file from project root"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write or overwrite a file with new content. Always read the file first if it exists.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the file"
                    },
                    "content": {
                        "type": "string",
                        "description": "Complete file content to write"
                    }
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_command",
            "description": "Execute a shell command. Use for git, npm, pip, pytest, etc. Be cautious with destructive commands.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Brief explanation of why this command is needed"
                    }
                },
                "required": ["command", "reason"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in a directory or search for files matching a pattern.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path to list (default: current directory)"
                    },
                    "pattern": {
                        "type": "string",
                        "description": "Optional glob pattern to filter files (e.g., '*.py')"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Search for text content across files in the project. Similar to grep.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Text to search for"
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": "Limit search to files matching pattern (e.g., '*.py')"
                    }
                },
                "required": ["query"]
            }
        }
    }
]

class PermissionMode:
    """Permission modes for agent actions"""
    NORMAL = "normal"      # Ask for everything
    AUTO_APPROVE = "auto"  # Auto-approve all
    PLAN = "plan"          # Read-only, no writes


class LocalAgent:
    """Main agent class - handles conversation loop and tool execution"""
    
    def __init__(self, 
                 model: str = "llama3.2",
                 project_dir: str = ".",
                 permission_mode: str = PermissionMode.NORMAL):
        self.model = model
        self.project_dir = Path(project_dir).resolve()
        self.permission_mode = permission_mode
        self.conversation_history = []
        self.session_start = datetime.now()
        
        # Initialize conversation history directory
        self.history_dir = Path.home() / ".localagent" / "sessions"
        self.history_dir.mkdir(parents=True, exist_ok=True)
        
        # Load project context
        self.project_context = self._load_project_context()
        
    def _load_project_context(self) -> str:
        """Load AGENT.md or README.md for project context"""
        context_files = ["AGENT.md", "CLAUDE.md", "README.md"]
        
        for filename in context_files:
            filepath = self.project_dir / filename
            if filepath.exists():
                try:
                    content = filepath.read_text()
                    console.print(f"[dim]📋 Loaded project context from {filename}[/dim]")
                    return content[:2000]  # Limit context size
                except:
                    pass
        return ""
    
    def _get_system_prompt(self) -> str:
        """Generate system prompt for the agent"""
        mode_instructions = {
            PermissionMode.NORMAL: "Ask for user approval before making changes.",
            PermissionMode.AUTO_APPROVE: "You can make changes without asking. Be careful!",
            PermissionMode.PLAN: "You are in PLAN MODE - read-only. Do not write files or execute commands. Only analyze and create plans."
        }
        
        return f"""You are a helpful coding assistant working in the directory: {self.project_dir}

Permission Mode: {self.permission_mode.upper()}
{mode_instructions[self.permission_mode]}

Project Context:
{self.project_context if self.project_context else "No project context file found."}

Guidelines:
1. ALWAYS read relevant files before making changes
2. Explain your plan before executing it
3. Write clean, well-documented code
4. When the task is complete, give a final summary without calling more tools
5. Use search_files to find relevant code when you don't know the file structure
6. Be conversational and helpful

Available tools: read_file, write_file, execute_command, list_files, search_files"""

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool and return result"""
        
        try:
            if tool_name == "read_file":
                return self._read_file(arguments["path"])
            
            elif tool_name == "write_file":
                return self._write_file(arguments["path"], arguments["content"])
            
            elif tool_name == "execute_command":
                return self._execute_command(
                    arguments["command"], 
                    arguments.get("reason", "")
                )
            
            elif tool_name == "list_files":
                return self._list_files(
                    arguments.get("path", "."),
                    arguments.get("pattern")
                )
            
            elif tool_name == "search_files":
                return self._search_files(
                    arguments["query"],
                    arguments.get("file_pattern")
                )
            
            else:
                return {"error": f"Unknown tool: {tool_name}"}
                
        except Exception as e:
            return {"error": str(e)}
    
    def _read_file(self, path: str) -> Dict[str, Any]:
        """Read file contents"""
        console.print(f"[cyan]📖 Reading:[/cyan] {path}")
        
        try:
            full_path = self.project_dir / path
            
            if not full_path.exists():
                return {"error": f"File not found: {path}"}
            
            content = full_path.read_text()
            
            # Show preview
            ext = full_path.suffix.lstrip('.') or "txt"
            preview_lines = content.split('\n')[:15]
            preview = '\n'.join(preview_lines)
            if len(content.split('\n')) > 15:
                preview += f"\n... ({len(content.split('\n')) - 15} more lines)"
            
            syntax = Syntax(preview, ext, theme="monokai", line_numbers=True)
            console.print(Panel(syntax, title=f"📄 {path}", border_style="cyan"))
            
            return {
                "success": True,
                "content": content,
                "lines": len(content.split('\n')),
                "size": len(content)
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def _write_file(self, path: str, content: str) -> Dict[str, Any]:
        """Write content to file"""
        
        if self.permission_mode == PermissionMode.PLAN:
            console.print("[yellow]⏸  PLAN MODE:[/yellow] Would write to", path)
            return {"success": False, "message": "Plan mode - no writes allowed"}
        
        console.print(f"[yellow]📝 Writing:[/yellow] {path}")
        
        try:
            full_path = self.project_dir / path
            
            # Show diff if file exists
            if full_path.exists():
                old_content = full_path.read_text()
                console.print(Panel(
                    f"[red]- Old ({len(old_content)} bytes)[/red]\n"
                    f"[green]+ New ({len(content)} bytes)[/green]",
                    title="📊 Changes"
                ))
            
            # Show preview of new content
            ext = full_path.suffix.lstrip('.') or "txt"
            preview_lines = content.split('\n')[:20]
            preview = '\n'.join(preview_lines)
            if len(content.split('\n')) > 20:
                preview += f"\n... ({len(content.split('\n')) - 20} more lines)"
            
            syntax = Syntax(preview, ext, theme="monokai", line_numbers=True)
            console.print(Panel(syntax, title=f"New content: {path}", border_style="yellow"))
            
            # Ask for approval
            if self.permission_mode == PermissionMode.NORMAL:
                if not Confirm.ask(f"[bold]Write to {path}?[/bold]"):
                    console.print("[red]✗[/red] Cancelled by user")
                    return {"success": False, "message": "Cancelled by user"}
            
            # Write file
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
            console.print(f"[green]✓[/green] Wrote {len(content)} bytes to {path}")
            
            return {"success": True, "bytes_written": len(content)}
            
        except Exception as e:
            return {"error": str(e)}
    
    def _execute_command(self, command: str, reason: str) -> Dict[str, Any]:
        """Execute shell command"""
        
        if self.permission_mode == PermissionMode.PLAN:
            console.print(f"[yellow]⏸  PLAN MODE:[/yellow] Would execute: {command}")
            return {"success": False, "message": "Plan mode - no commands allowed"}
        
        console.print(f"[blue]🔧 Command:[/blue] {command}")
        console.print(f"[dim]Reason: {reason}[/dim]")
        
        # Safety check
        dangerous = ['rm -rf /', 'rm -rf ~', 'sudo rm', 'mkfs', 'dd if=', ':(){ :|:& };:']
        if any(d in command.lower() for d in dangerous):
            console.print("[red]🛑 BLOCKED:[/red] Dangerous command detected")
            return {"error": "Dangerous command blocked for safety"}
        
        # Ask for approval
        if self.permission_mode == PermissionMode.NORMAL:
            if not Confirm.ask(f"[bold]Execute: {command}?[/bold]"):
                console.print("[red]✗[/red] Cancelled by user")
                return {"success": False, "message": "Cancelled by user"}
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=self.project_dir,
                timeout=30
            )
            
            output = result.stdout + result.stderr
            
            if result.returncode == 0:
                console.print(Panel(
                    output or "[dim]Command completed successfully[/dim]",
                    title="✓ Output",
                    border_style="green"
                ))
            else:
                console.print(Panel(
                    output,
                    title=f"✗ Failed (exit code {result.returncode})",
                    border_style="red"
                ))
            
            return {
                "success": result.returncode == 0,
                "output": output,
                "exit_code": result.returncode
            }
            
        except subprocess.TimeoutExpired:
            return {"error": "Command timed out after 30 seconds"}
        except Exception as e:
            return {"error": str(e)}
    
    def _list_files(self, path: str = ".", pattern: Optional[str] = None) -> Dict[str, Any]:
        """List files in directory"""
        try:
            full_path = self.project_dir / path
            
            if pattern:
                files = [str(f.relative_to(full_path)) 
                        for f in full_path.rglob(pattern)]
            else:
                files = [f.name for f in full_path.iterdir() 
                        if not f.name.startswith('.')]
            
            # Display as table
            table = Table(title=f"📁 {path}")
            table.add_column("Files", style="cyan")
            
            for f in sorted(files)[:30]:
                table.add_row(f)
            
            if len(files) > 30:
                table.add_row(f"[dim]... and {len(files) - 30} more[/dim]")
            
            console.print(table)
            
            return {"success": True, "files": files, "count": len(files)}
            
        except Exception as e:
            return {"error": str(e)}
    
    def _search_files(self, query: str, file_pattern: Optional[str] = None) -> Dict[str, Any]:
        """Search for text in files"""
        console.print(f"[cyan]🔍 Searching for:[/cyan] '{query}'")
        
        try:
            # Use ripgrep if available, otherwise fallback to grep
            pattern_arg = f"-g '{file_pattern}'" if file_pattern else ""
            
            # Try ripgrep first
            try:
                result = subprocess.run(
                    f"rg -n -C 2 {pattern_arg} '{query}'",
                    shell=True,
                    capture_output=True,
                    text=True,
                    cwd=self.project_dir,
                    timeout=10
                )
            except:
                # Fallback to grep
                result = subprocess.run(
                    f"grep -rn '{query}' .",
                    shell=True,
                    capture_output=True,
                    text=True,
                    cwd=self.project_dir,
                    timeout=10
                )
            
            output = result.stdout
            
            if output:
                # Limit output
                lines = output.split('\n')[:50]
                preview = '\n'.join(lines)
                if len(output.split('\n')) > 50:
                    preview += f"\n... ({len(output.split('\n')) - 50} more matches)"
                
                console.print(Panel(preview, title="Search Results", border_style="cyan"))
                
                return {
                    "success": True,
                    "results": output,
                    "match_count": len([l for l in output.split('\n') if l.strip()])
                }
            else:
                console.print("[dim]No matches found[/dim]")
                return {"success": True, "results": "", "match_count": 0}
                
        except Exception as e:
            return {"error": str(e)}
    
    def run_interactive(self):
        """Run interactive REPL session"""
        
        # Print welcome banner
        banner = Panel(
            f"[bold cyan]LocalAgent[/bold cyan] - Autonomous Coding Assistant\n\n"
            f"📂 Project: [cyan]{self.project_dir.name}[/cyan]\n"
            f"🤖 Model: [cyan]{self.model}[/cyan]\n"
            f"🔒 Mode: [cyan]{self.permission_mode}[/cyan]\n\n"
            f"[dim]Type your requests in natural language or /help for commands[/dim]",
            title="🚀 Ready",
            border_style="cyan"
        )
        console.print(banner)
        
        # Set up prompt with history
        history_file = self.history_dir / "history.txt"
        session = PromptSession(history=FileHistory(str(history_file)))
        
        # Initialize conversation
        self.conversation_history = [
            {"role": "system", "content": self._get_system_prompt()}
        ]
        
        # Main loop
        while True:
            try:
                # Get user input
                user_input = session.prompt("\n> ", multiline=False)
                
                if not user_input.strip():
                    continue
                
                # Handle commands
                if user_input.startswith('/'):
                    self._handle_command(user_input)
                    continue
                
                # Process with agent
                self._process_message(user_input)
                
            except KeyboardInterrupt:
                if Confirm.ask("\n[yellow]Exit LocalAgent?[/yellow]"):
                    console.print("[cyan]👋 Goodbye![/cyan]")
                    break
            except EOFError:
                break
    
    def _handle_command(self, command: str):
        """Handle special commands"""
        cmd = command.lower().strip()
        
        if cmd == '/help':
            help_text = """
[bold cyan]Commands:[/bold cyan]
  /help              Show this help
  /clear             Clear conversation history
  /mode [normal|auto|plan]  Change permission mode
  /project           Show project info
  /exit              Exit LocalAgent

[bold cyan]Tips:[/bold cyan]
  - Be specific about what you want
  - Agent will read files before editing
  - Use plan mode to explore without changes
  - Press Ctrl+C to interrupt
"""
            console.print(Panel(help_text, title="Help"))
        
        elif cmd == '/clear':
            self.conversation_history = [
                {"role": "system", "content": self._get_system_prompt()}
            ]
            console.print("[green]✓[/green] Conversation cleared")
        
        elif cmd.startswith('/mode'):
            parts = cmd.split()
            if len(parts) > 1:
                mode = parts[1]
                if mode in [PermissionMode.NORMAL, PermissionMode.AUTO_APPROVE, PermissionMode.PLAN]:
                    self.permission_mode = mode
                    console.print(f"[green]✓[/green] Mode changed to: {mode}")
                else:
                    console.print("[red]Invalid mode. Use: normal, auto, or plan[/red]")
            else:
                console.print(f"Current mode: {self.permission_mode}")
        
        elif cmd == '/project':
            info = f"""
[bold]Project Information[/bold]
Path: {self.project_dir}
Mode: {self.permission_mode}
Model: {self.model}
Session: {(datetime.now() - self.session_start).seconds // 60} minutes
"""
            console.print(Panel(info, title="Project"))
        
        elif cmd == '/exit':
            raise KeyboardInterrupt
        
        else:
            console.print(f"[red]Unknown command: {command}[/red]")
            console.print("[dim]Type /help for available commands[/dim]")
    
    def _process_message(self, user_message: str):
        """Process a user message through the agent loop"""
        
        # Add to conversation
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })
        
        # Agent loop
        max_iterations = 15
        
        for iteration in range(max_iterations):
            console.print(f"[dim]{'─' * 60}[/dim]")
            
            try:
                # Show thinking indicator
                with console.status("[cyan]🤔 Thinking...[/cyan]", spinner="dots"):
                    response = ollama.chat(
                        model=self.model,
                        messages=self.conversation_history,
                        tools=TOOLS
                    )
                
                # Add assistant response
                self.conversation_history.append(response["message"])
                
                # Check if using tools
                if response["message"].get("tool_calls"):
                    # Execute tools
                    for tool_call in response["message"]["tool_calls"]:
                        tool_name = tool_call["function"]["name"]
                        arguments = tool_call["function"]["arguments"]
                        
                        # Execute
                        result = self.execute_tool(tool_name, arguments)
                        
                        # Add result to conversation
                        self.conversation_history.append({
                            "role": "tool",
                            "content": json.dumps(result)
                        })
                else:
                    # No more tools - final response
                    final_text = response["message"].get("content", "")
                    
                    if final_text:
                        console.print(Panel(
                            Markdown(final_text),
                            title="[bold green]🤖 LocalAgent[/bold green]",
                            border_style="green"
                        ))
                    
                    return
                    
            except Exception as e:
                console.print(f"[red]Error:[/red] {e}")
                import traceback
                console.print("[dim]" + traceback.format_exc() + "[/dim]")
                return
        
        console.print("[yellow]⚠️  Reached maximum iterations[/yellow]")
    
    def run_oneshot(self, prompt: str):
        """Run a single prompt and exit"""
        console.print(Panel(f"[cyan]Task:[/cyan] {prompt}", title="One-shot Mode"))
        
        self.conversation_history = [
            {"role": "system", "content": self._get_system_prompt()},
            {"role": "user", "content": prompt}
        ]
        
        self._process_message(prompt)


def main():
    parser = argparse.ArgumentParser(
        description="LocalAgent - Autonomous coding assistant with local models"
    )
    parser.add_argument(
        "--model", "-m",
        default="llama3.2",
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
    
    args = parser.parse_args()
    
    # Check Ollama connection
    try:
        ollama.list()
    except:
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
    
    # Determine permission mode
    if args.auto_approve:
        permission_mode = PermissionMode.AUTO_APPROVE
    elif args.plan_mode:
        permission_mode = PermissionMode.PLAN
    else:
        permission_mode = PermissionMode.NORMAL
    
    # Create agent
    agent = LocalAgent(
        model=args.model,
        project_dir=os.getcwd(),
        permission_mode=permission_mode
    )
    
    # Run
    if args.prompt:
        agent.run_oneshot(args.prompt)
    else:
        agent.run_interactive()


if __name__ == "__main__":
    main()
