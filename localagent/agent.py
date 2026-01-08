"""Main LocalAgent class"""

import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

import ollama
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from .models import PermissionMode
from .config import AgentConfig
from .core.conversation import ConversationManager
from .core.streaming import stream_ollama_response, display_streaming_response
from .core.security import SecurityError
from .tools import TOOLS, create_tool_instance
from .ui.console import console
from .utils.errors import retry_with_backoff, ModelError

try:
    from .core.streaming import stream_ollama_response, display_streaming_response
except ImportError:
    # Fallback if streaming not available
    stream_ollama_response = None
    display_streaming_response = None


class LocalAgent:
    """Main agent class - handles conversation loop and tool execution"""
    
    def __init__(
        self,
        model: str = "llama3.2",
        project_dir: str = ".",
        permission_mode: str = PermissionMode.NORMAL,
        config: Optional[AgentConfig] = None
    ):
        self.model = model
        self.project_dir = Path(project_dir).resolve()
        self.permission_mode = permission_mode
        self.config = config or AgentConfig()
        self.session_start = datetime.now()
        
        # Initialize conversation manager
        system_prompt = self._get_system_prompt()
        self.conversation = ConversationManager(
            system_prompt=system_prompt,
            max_tokens=self.config.max_tokens,
            keep_recent=self.config.keep_recent_messages
        )
        
        # Initialize history directory
        self.history_dir = Path.home() / ".localagent" / "sessions"
        self.history_dir.mkdir(parents=True, exist_ok=True)
        
        # Load project context
        self.project_context = self._load_project_context()
        
        # Update system prompt with context
        self.conversation.history[0]["content"] = self._get_system_prompt()
    
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

Available tools: read_file, write_file, execute_command, list_files, search_files, git_status, git_diff, git_commit, git_log, run_tests"""
    
    @retry_with_backoff(max_retries=3, exceptions=(Exception,))
    def _call_model(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Call Ollama model with retry logic"""
        try:
            return ollama.chat(
                model=self.model,
                messages=messages,
                tools=tools
            )
        except Exception as e:
            raise ModelError(f"Failed to call model: {e}") from e
    
    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool and return result"""
        
        # Fix: Handle string arguments (JSON)
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                return {"error": f"Invalid JSON in tool arguments: {arguments}"}
        
        try:
            # Create tool instance
            tool = create_tool_instance(
                tool_name,
                self.project_dir,
                self.permission_mode,
                console
            )
            
            # Execute tool
            return tool.execute(**arguments)
            
        except ValueError as e:
            return {"error": f"Unknown tool: {tool_name}"}
        except SecurityError as e:
            return {"error": str(e)}
        except Exception as e:
            return {"error": str(e)}
    
    def _process_message(self, user_message: str, use_streaming: bool = False):
        """Process a user message through the agent loop"""
        
        # Add user message
        self.conversation.add_user_message(user_message)
        
        # Agent loop
        max_iterations = self.config.max_iterations
        
        for iteration in range(max_iterations):
            console.print(f"[dim]{'─' * 60}[/dim]")
            
            try:
                # Get conversation history
                messages = self.conversation.get_history()
                
                # Show thinking indicator
                with console.status("[cyan]🤔 Thinking...[/cyan]", spinner="dots"):
                    if use_streaming and stream_ollama_response:
                        # Streaming mode
                        stream = stream_ollama_response(
                            self.model,
                            messages,
                            TOOLS
                        )
                        response_message = display_streaming_response(stream)
                    else:
                        # Non-streaming mode
                        response = self._call_model(messages, TOOLS)
                        response_message = response["message"]
                
                # Add assistant response
                self.conversation.add_assistant_message(
                    content=response_message.get("content", ""),
                    tool_calls=response_message.get("tool_calls")
                )
                
                # Check if using tools
                if response_message.get("tool_calls"):
                    # Execute tools
                    for tool_call in response_message["tool_calls"]:
                        tool_name = tool_call["function"]["name"]
                        arguments = tool_call["function"]["arguments"]
                        
                        # Execute
                        result = self.execute_tool(tool_name, arguments)
                        
                        # Add result to conversation
                        tool_call_id = tool_call.get("id", f"call_{iteration}")
                        self.conversation.add_tool_result(tool_call_id, result)
                else:
                    # No more tools - final response
                    final_text = response_message.get("content", "")
                    
                    if final_text:
                        console.print(Panel(
                            Markdown(final_text),
                            title="[bold green]🤖 LocalAgent[/bold green]",
                            border_style="green"
                        ))
                    
                    return
                    
            except ModelError as e:
                console.print(f"[red]Model Error:[/red] {e}")
                import traceback
                console.print("[dim]" + traceback.format_exc() + "[/dim]")
                return
            except Exception as e:
                console.print(f"[red]Error:[/red] {e}")
                import traceback
                console.print("[dim]" + traceback.format_exc() + "[/dim]")
                return
        
        console.print("[yellow]⚠️  Reached maximum iterations[/yellow]")
    
    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """Get current conversation history"""
        return self.conversation.get_history()
    
    def clear_conversation(self) -> None:
        """Clear conversation history"""
        self.conversation.clear(keep_system=True)
        # Update system prompt
        self.conversation.history[0]["content"] = self._get_system_prompt()

