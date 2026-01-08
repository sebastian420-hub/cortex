"""File search and listing tools"""

import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .base import Tool
from ..core.security import validate_path, SecurityError


class ListFilesTool(Tool):
    """Tool for listing files in directories"""
    
    def execute(self, path: str = ".", pattern: Optional[str] = None) -> Dict[str, Any]:
        """List files in directory"""
        try:
            full_path = validate_path(self.project_dir, path)
            
            if not full_path.exists():
                return {"error": f"Path not found: {path}"}
            
            if not full_path.is_dir():
                return {"error": f"Path is not a directory: {path}"}
            
            if pattern:
                files = [str(f.relative_to(full_path)) 
                        for f in full_path.rglob(pattern)]
            else:
                files = [f.name for f in full_path.iterdir() 
                        if not f.name.startswith('.')]
            
            # Display as table
            if self.console:
                table = Table(title=f"📁 {path}")
                table.add_column("Files", style="cyan")
                
                for f in sorted(files)[:30]:
                    table.add_row(f)
                
                if len(files) > 30:
                    table.add_row(f"[dim]... and {len(files) - 30} more[/dim]")
                
                self.console.print(table)
            
            return {"success": True, "files": files, "count": len(files)}
            
        except SecurityError as e:
            return {"error": str(e)}
        except Exception as e:
            return {"error": str(e)}


class SearchFilesTool(Tool):
    """Tool for searching text in files"""
    
    def execute(self, query: str, file_pattern: Optional[str] = None) -> Dict[str, Any]:
        """Search for text in files"""
        if self.console:
            self.console.print(f"[cyan]🔍 Searching for:[/cyan] '{query}'")
        
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
                output_lines = output.split('\n')
                lines = output_lines[:50]
                preview = '\n'.join(lines)
                if len(output_lines) > 50:
                    more_matches = len(output_lines) - 50
                    preview += f"\n... ({more_matches} more matches)"
                
                if self.console:
                    self.console.print(Panel(preview, title="Search Results", border_style="cyan"))
                
                return {
                    "success": True,
                    "results": output,
                    "match_count": len([l for l in output.split('\n') if l.strip()])
                }
            else:
                if self.console:
                    self.console.print("[dim]No matches found[/dim]")
                return {"success": True, "results": "", "match_count": 0}
                
        except Exception as e:
            return {"error": str(e)}

