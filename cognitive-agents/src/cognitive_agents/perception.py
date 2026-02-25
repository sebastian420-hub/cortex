from __future__ import annotations

import os
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

@dataclass
class Perception:
    """A generic container for perception data."""
    data: dict[str, Any]

class PerceptionInterface(ABC):
    """
    An abstract base class that defines the contract for how an agent perceives its environment.
    """

    @abstractmethod
    def perceive(self) -> Perception:
        """
        Perceive the environment and return a Perception object.
        """
        pass

class GridPerception(PerceptionInterface):
    """
    A concrete implementation of PerceptionInterface for a grid-based environment.
    """

    def __init__(self, world: Any, position: tuple[int, int]):
        self.world = world
        self.position = position

    def perceive(self) -> Perception:
        # This will be implemented later, as it depends on the ai-ecosystem's World
        return Perception(data={})

class FilesystemPerception(PerceptionInterface):
    """
    A concrete implementation of PerceptionInterface for a filesystem-based environment.
    """

    def __init__(self, root_path: str):
        self.root_path = root_path

    def perceive(self, max_file_size=1024 * 10) -> Perception:
        files = []
        file_contents = {}
        key_files = ["README.md", "pyproject.toml", "setup.py", "main.py", "cli.py", "app.py"]

        for root, _, filenames in os.walk(self.root_path):
            for filename in filenames:
                file_path = os.path.join(root, filename)
                files.append(file_path)

                if filename in key_files:
                    try:
                        if os.path.getsize(file_path) < max_file_size:
                            with open(file_path, "r", encoding="utf-8") as f:
                                file_contents[file_path] = f.read()
                    except (IOError, OSError, UnicodeDecodeError):
                        pass

        try:
            git_status = subprocess.check_output(["git", "status", "--porcelain"], cwd=self.root_path, text=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            git_status = ""
        
        return Perception(data={"files": files, "git_status": git_status, "file_contents": file_contents})
