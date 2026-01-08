"""Session persistence for LocalAgent"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from rich.console import Console
from rich.table import Table

console = Console()


class SessionManager:
    """Manages saving and loading conversation sessions"""
    
    def __init__(self, sessions_dir: Path):
        self.sessions_dir = sessions_dir
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
    
    def save_session(
        self,
        session_name: str,
        conversation_history: List[Dict[str, Any]],
        project_dir: str,
        model: str,
        permission_mode: str
    ) -> bool:
        """
        Save a conversation session.
        
        Args:
            session_name: Name for the session
            conversation_history: Full conversation history
            project_dir: Project directory path
            model: Model name used
            permission_mode: Permission mode used
            
        Returns:
            True if saved successfully
        """
        try:
            # Sanitize session name
            safe_name = "".join(c for c in session_name if c.isalnum() or c in ('-', '_'))
            if not safe_name:
                safe_name = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            session_file = self.sessions_dir / f"{safe_name}.json"
            
            session_data = {
                "session_name": safe_name,
                "conversation_history": conversation_history,
                "project_dir": project_dir,
                "model": model,
                "permission_mode": permission_mode,
                "created_at": datetime.now().isoformat(),
                "version": "1.0"
            }
            
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
            
            console.print(f"[green]✓[/green] Session saved: {safe_name}")
            return True
            
        except Exception as e:
            console.print(f"[red]Error saving session:[/red] {e}")
            return False
    
    def load_session(self, session_name: str) -> Optional[Dict[str, Any]]:
        """
        Load a conversation session.
        
        Args:
            session_name: Name of the session to load
            
        Returns:
            Session data or None if not found
        """
        try:
            # Try with and without .json extension
            session_file = self.sessions_dir / session_name
            if not session_file.exists():
                session_file = self.sessions_dir / f"{session_name}.json"
            
            if not session_file.exists():
                console.print(f"[red]Session not found:[/red] {session_name}")
                return None
            
            with open(session_file, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            
            console.print(f"[green]✓[/green] Session loaded: {session_name}")
            return session_data
            
        except Exception as e:
            console.print(f"[red]Error loading session:[/red] {e}")
            return None
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """
        List all saved sessions.
        
        Returns:
            List of session metadata
        """
        sessions = []
        
        for session_file in self.sessions_dir.glob("*.json"):
            try:
                with open(session_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    sessions.append({
                        "name": session_file.stem,
                        "created_at": data.get("created_at", "Unknown"),
                        "model": data.get("model", "Unknown"),
                        "project_dir": data.get("project_dir", "Unknown")
                    })
            except:
                continue
        
        # Sort by creation time (newest first)
        sessions.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return sessions
    
    def show_sessions(self) -> None:
        """Display all sessions in a table"""
        sessions = self.list_sessions()
        
        if not sessions:
            console.print("[dim]No saved sessions[/dim]")
            return
        
        table = Table(title="📚 Saved Sessions")
        table.add_column("Name", style="cyan")
        table.add_column("Created", style="green")
        table.add_column("Model", style="yellow")
        table.add_column("Project", style="blue")
        
        for session in sessions:
            table.add_row(
                session["name"],
                session["created_at"][:19] if len(session["created_at"]) > 19 else session["created_at"],
                session["model"],
                Path(session["project_dir"]).name
            )
        
        console.print(table)
    
    def delete_session(self, session_name: str) -> bool:
        """
        Delete a saved session.
        
        Args:
            session_name: Name of session to delete
            
        Returns:
            True if deleted successfully
        """
        try:
            session_file = self.sessions_dir / f"{session_name}.json"
            if session_file.exists():
                session_file.unlink()
                console.print(f"[green]✓[/green] Session deleted: {session_name}")
                return True
            else:
                console.print(f"[red]Session not found:[/red] {session_name}")
                return False
        except Exception as e:
            console.print(f"[red]Error deleting session:[/red] {e}")
            return False

