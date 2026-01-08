"""Test execution tools"""

import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
from rich.console import Console
from rich.panel import Panel

from .base import Tool


class RunTestsTool(Tool):
    """Tool for running tests"""
    
    def _detect_test_framework(self) -> Optional[str]:
        """Detect which test framework is being used"""
        # Check for pytest
        if (self.project_dir / "pytest.ini").exists() or \
           (self.project_dir / "pyproject.toml").exists():
            # Check if pytest is mentioned in pyproject.toml
            try:
                # Try tomllib (Python 3.11+)
                try:
                    import tomllib
                    with open(self.project_dir / "pyproject.toml", "rb") as f:
                        config = tomllib.load(f)
                        if "tool" in config and "pytest" in config["tool"]:
                            return "pytest"
                except ImportError:
                    # Fallback to tomli for older Python
                    try:
                        import tomli
                        with open(self.project_dir / "pyproject.toml", "rb") as f:
                            config = tomli.load(f)
                            if "tool" in config and "pytest" in config["tool"]:
                                return "pytest"
                    except ImportError:
                        pass
            except:
                pass
        
        # Check for unittest
        if (self.project_dir / "tests").exists() or \
           (self.project_dir / "test").exists():
            # Check for unittest-style files
            test_dirs = [
                self.project_dir / "tests",
                self.project_dir / "test"
            ]
            for test_dir in test_dirs:
                if test_dir.exists():
                    for f in test_dir.rglob("test_*.py"):
                        return "unittest"  # Could be unittest or pytest
        
        # Default to pytest if available
        try:
            subprocess.run(["pytest", "--version"], capture_output=True, timeout=2)
            return "pytest"
        except:
            pass
        
        return None
    
    def execute(self, pattern: Optional[str] = None, verbose: bool = False) -> Dict[str, Any]:
        """Run test suite"""
        framework = self._detect_test_framework()
        
        if not framework:
            return {"error": "Could not detect test framework. Install pytest or use unittest."}
        
        if self.console:
            self.console.print(f"[blue]🧪 Running tests with {framework}...[/blue]")
        
        try:
            if framework == "pytest":
                cmd = ["pytest"]
                if pattern:
                    cmd.append(pattern)
                if verbose:
                    cmd.append("-v")
            else:  # unittest
                import unittest
                cmd = ["python", "-m", "unittest", "discover"]
                if pattern:
                    cmd.extend(["-p", pattern])
                if verbose:
                    cmd.append("-v")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.project_dir,
                timeout=120  # Tests can take longer
            )
            
            output = result.stdout + result.stderr
            
            if self.console:
                border_style = "green" if result.returncode == 0 else "red"
                title = "✓ Tests Passed" if result.returncode == 0 else "✗ Tests Failed"
                self.console.print(Panel(
                    output,
                    title=title,
                    border_style=border_style
                ))
            
            return {
                "success": result.returncode == 0,
                "output": output,
                "exit_code": result.returncode,
                "framework": framework
            }
        except subprocess.TimeoutExpired:
            return {"error": "Tests timed out after 120 seconds"}
        except Exception as e:
            return {"error": str(e)}

