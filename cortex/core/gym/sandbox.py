"""Sandbox provider for Cognitive Gym.

Handles creation, management and cleanup of isolated practice environments.
"""

import shutil
import tempfile
import logging
from pathlib import Path
from typing import Optional, List, Union

logger = logging.getLogger(__name__)

class SandboxProvider:
    """
    Manages isolated filesystem sandboxes for agent practice.
    """

    def __init__(self, base_project_dir: Path):
        """
        Initialize sandbox provider.

        Args:
            base_project_dir: The original project directory to clone from.
        """
        self.base_project_dir = Path(base_project_dir).resolve()
        self.active_sandboxes: List[Path] = []

    def create_sandbox(self, name_prefix: str = "cortex_gym_") -> Path:
        """
        Create a new sandbox by cloning the base project.

        Returns:
            Path to the new sandbox directory.
        """
        # Create a temporary directory
        temp_dir = Path(tempfile.mkdtemp(prefix=name_prefix))
        
        logger.info(f"Creating sandbox at {temp_dir} from {self.base_project_dir}")
        
        try:
            # Clone the project
            # Use a helper to skip .git and other large/unnecessary folders if needed
            self._clone_project(self.base_project_dir, temp_dir)
            
            self.active_sandboxes.append(temp_dir)
            return temp_dir
        except Exception as e:
            logger.error(f"Failed to create sandbox: {e}")
            # Cleanup on failure
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            raise

    def restore_sandbox(self, sandbox_path: Path) -> None:
        """
        Restore a sandbox to the original state of the base project.
        """
        if sandbox_path not in self.active_sandboxes:
            raise ValueError(f"Path {sandbox_path} is not an active sandbox managed by this provider.")
            
        logger.info(f"Restoring sandbox {sandbox_path}")
        
        # Clear current contents
        for item in sandbox_path.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
                
        # Re-clone
        self._clone_project(self.base_project_dir, sandbox_path)

    def cleanup_sandbox(self, sandbox_path: Path) -> None:
        """
        Remove a sandbox directory and its contents.
        """
        if sandbox_path in self.active_sandboxes:
            logger.info(f"Cleaning up sandbox {sandbox_path}")
            if sandbox_path.exists():
                shutil.rmtree(sandbox_path)
            self.active_sandboxes.remove(sandbox_path)

    def cleanup_all(self) -> None:
        """
        Clean up all active sandboxes.
        """
        for sandbox in list(self.active_sandboxes):
            self.cleanup_sandbox(sandbox)

    def _clone_project(self, src: Path, dst: Path) -> None:
        """
        Internal helper to clone the project while skipping unnecessary files.
        """
        ignore_patterns = shutil.ignore_patterns(
            ".git", ".pytest_cache", "__pycache__", ".mypy_cache", 
            "node_modules", "dist", "build", ".venv", "venv"
        )
        
        # We use copytree but we need to handle the case where dst already exists (tempfile.mkdtemp creates it)
        # So we copy the contents of src to dst
        for item in src.iterdir():
            if item.name in [".git", ".pytest_cache", "__pycache__", ".mypy_cache", "node_modules", "dist", "build", ".venv", "venv"]:
                continue
                
            s = src / item.name
            d = dst / item.name
            if s.is_dir():
                shutil.copytree(s, d, ignore=ignore_patterns)
            else:
                shutil.copy2(s, d)
