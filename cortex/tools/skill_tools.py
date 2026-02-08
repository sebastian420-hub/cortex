"""Skill loader tool for managing and applying development skills."""

import logging
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .base import Tool
from ..utils.errors import create_error_response, create_success_response, ErrorType

logger = logging.getLogger(__name__)


class SkillCategory(str, Enum):
    """Categories of development skills."""

    TESTING = "testing"
    REFACTORING = "refactoring"
    DEBUGGING = "debugging"
    MIGRATION = "migration"
    OPTIMIZATION = "optimization"
    DOCUMENTATION = "documentation"
    SECURITY = "security"
    DEPLOYMENT = "deployment"
    GENERAL = "general"


@dataclass
class Skill:
    """A development skill that can be applied to tasks."""

    name: str
    description: str
    category: SkillCategory
    file_path: Path
    content: str
    prerequisites: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    difficulty: int = 1  # 1=easy, 5=expert
    estimated_time_minutes: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert skill to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "file_path": str(self.file_path),
            "prerequisites": self.prerequisites,
            "tags": self.tags,
            "difficulty": self.difficulty,
            "estimated_time_minutes": self.estimated_time_minutes,
        }

    def get_workflow_steps(self) -> List[str]:
        """Extract workflow steps from skill content."""
        steps = []
        in_steps_section = False

        for line in self.content.split("\n"):
            if line.startswith("## Skill Steps"):
                in_steps_section = True
                continue
            elif in_steps_section and line.startswith("## "):
                # Next section reached
                break
            elif in_steps_section and line.strip() and line.startswith("###"):
                # Step header
                steps.append(line.strip().replace("### ", ""))
            elif in_steps_section and line.strip() and line.startswith("-"):
                # Step detail
                steps.append(line.strip().replace("- ", ""))

        return steps

    def get_tool_patterns(self) -> Dict[str, List[str]]:
        """Extract tool usage patterns from skill content."""
        patterns = {}
        current_tool = None

        for line in self.content.split("\n"):
            if line.startswith("### ") and "Tool" in line:
                current_tool = line.replace("### ", "").lower()
                patterns[current_tool] = []
            elif current_tool and "```python" in line:
                # Start of code block
                pass
            elif current_tool and line.strip() == "```":
                # End of code block
                current_tool = None
            elif current_tool and line.strip() and not line.startswith("```"):
                patterns[current_tool].append(line)

        return patterns

    def is_applicable(
        self, task_description: str, context: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        Determine how applicable this skill is to a task.

        Returns a score from 0.0 to 1.0.
        """
        task_lower = task_description.lower()
        skill_text = (self.name + " " + self.description + " " + " ".join(self.tags)).lower()

        # Check for keyword matches
        keywords = set(skill_text.split())
        task_words = set(task_lower.split())

        # Simple keyword overlap scoring
        if not keywords or not task_words:
            return 0.0

        overlap = len(keywords & task_words)
        total_unique = len(keywords | task_words)

        base_score = overlap / total_unique if total_unique > 0 else 0.0

        # Boost score if category keywords match
        category_boosters = {
            SkillCategory.TESTING: ["test", "tests", "testing", "tdd", "unit", "integration"],
            SkillCategory.REFACTORING: ["refactor", "clean", "improve", "restructure", "design"],
            SkillCategory.DEBUGGING: ["debug", "fix", "error", "bug", "issue", "crash"],
            SkillCategory.MIGRATION: ["migrate", "upgrade", "update", "version", "deprecate"],
            SkillCategory.OPTIMIZATION: ["optimize", "performance", "speed", "memory", "fast"],
            SkillCategory.DOCUMENTATION: ["document", "readme", "comment", "docstring", "guide"],
        }

        if self.category in category_boosters:
            for booster in category_boosters[self.category]:
                if booster in task_lower:
                    base_score += 0.2
                    break

        return min(1.0, base_score)


class SkillLoaderTool(Tool):
    """
    Tool for loading and managing development skills.

    Skills are documented workflows for common development tasks
    like TDD, refactoring, debugging, etc.
    """

    timeout_category = "skill"
    default_timeout = 10

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.skills: Dict[str, Skill] = {}
        self.skills_loaded = False
        self.skills_dir = self.project_dir / "cortex" / "skills"

        # Fallback to local skills directory if project skills doesn't exist
        if not self.skills_dir.exists():
            self.skills_dir = Path(__file__).parent.parent / "skills"

    def execute(
        self,
        action: str = "list",
        skill_name: Optional[str] = None,
        task_description: Optional[str] = None,
        limit: int = 5,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Execute skill loader operations.

        Args:
            action: Action to perform - "list", "load", "suggest", "get"
            skill_name: Name of skill (for load/get actions)
            task_description: Task description (for suggest action)
            limit: Maximum number of skills to return (for list/suggest)

        Returns:
            Dictionary with results
        """
        if not self.skills_loaded:
            self._load_skills()

        try:
            if action == "list":
                return self._list_skills(limit=limit)
            elif action == "load":
                if not skill_name:
                    return create_error_response(
                        "Skill name required for load action",
                        ErrorType.VALIDATION,
                        {"action": action},
                    )
                return self._load_skill(skill_name)
            elif action == "suggest":
                if not task_description:
                    return create_error_response(
                        "Task description required for suggest action",
                        ErrorType.VALIDATION,
                        {"action": action},
                    )
                return self._suggest_skills(task_description, limit=limit)
            elif action == "get":
                if not skill_name:
                    return create_error_response(
                        "Skill name required for get action",
                        ErrorType.VALIDATION,
                        {"action": action},
                    )
                return self._get_skill(skill_name)
            else:
                return create_error_response(
                    f"Unknown action: {action}. Must be one of: list, load, suggest, get",
                    ErrorType.VALIDATION,
                    {"action": action},
                )
        except Exception as e:
            logger.exception(f"Error in SkillLoaderTool.execute: {e}")
            return create_error_response(
                f"Skill operation failed: {str(e)}",
                ErrorType.EXECUTION,
                {"action": action, "skill_name": skill_name},
            )

    def _load_skills(self) -> None:
        """Load all skills from the skills directory."""
        if not self.skills_dir.exists():
            logger.warning(f"Skills directory not found: {self.skills_dir}")
            self.skills_loaded = True
            return

        logger.debug(f"Looking for skills in: {self.skills_dir}")
        logger.debug(f"Skills dir exists: {self.skills_dir.exists()}")

        for skill_file in self.skills_dir.glob("*.md"):
            logger.debug(f"Found skill file: {skill_file}")
            try:
                skill = self._parse_skill_file(skill_file)
                self.skills[skill.name] = skill
                logger.debug(f"Loaded skill: {skill.name}")
            except Exception as e:
                logger.error(f"Failed to parse skill file {skill_file}: {e}")

        self.skills_loaded = True
        logger.info(f"Loaded {len(self.skills)} skills from {self.skills_dir}")

    def _parse_skill_file(self, file_path: Path) -> Skill:
        """Parse a markdown skill file into a Skill object."""
        content = file_path.read_text(encoding="utf-8", errors="ignore")

        # Extract skill name from filename and header
        skill_name = file_path.stem.replace("_", " ").title()

        # Default values
        description = ""
        category = SkillCategory.GENERAL
        prerequisites = []
        tags = []
        difficulty = 1

        # Parse markdown headers
        lines = content.split("\n")
        in_code_block = False

        for i, line in enumerate(lines):
            # Skip lines inside code blocks
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue

            if line.startswith("# "):
                # Main title - use as skill name
                skill_name = line.replace("# ", "").strip()
            elif line.startswith("## Overview"):
                # Overview section - next line is usually description
                if i + 1 < len(lines) and lines[i + 1].strip():
                    description = lines[i + 1].strip()
            elif line.startswith("## When to Use"):
                # Extract tags from when to use section
                j = i + 1
                while j < len(lines) and not lines[j].startswith("## "):
                    # Check if we enter a code block
                    if lines[j].strip().startswith("```"):
                        # Skip to end of code block
                        j += 1
                        while j < len(lines) and not lines[j].strip().startswith("```"):
                            j += 1
                        if j < len(lines):
                            j += 1
                        continue

                    if lines[j].strip().startswith("-"):
                        tag = lines[j].strip().replace("- ", "").split()[0].lower()
                        tags.append(tag)
                    j += 1

        # Determine category from filename and content
        file_lower = file_path.stem.lower()
        content_lower = content.lower()

        if any(word in file_lower or word in content_lower for word in ["test", "tdd"]):
            category = SkillCategory.TESTING
        elif any(word in file_lower or word in content_lower for word in ["refactor", "clean"]):
            category = SkillCategory.REFACTORING
        elif any(word in file_lower or word in content_lower for word in ["debug", "fix", "bug"]):
            category = SkillCategory.DEBUGGING
        elif any(
            word in file_lower or word in content_lower for word in ["migrate", "api", "upgrade"]
        ):
            category = SkillCategory.MIGRATION
        elif any(
            word in file_lower or word in content_lower for word in ["optimize", "performance"]
        ):
            category = SkillCategory.OPTIMIZATION

        # Extract prerequisites if mentioned
        if "prereq" in content_lower or "requirement" in content_lower:
            for line in lines:
                if "prereq" in line.lower() or "requirement" in line.lower():
                    if ":" in line:
                        prereq_text = line.split(":", 1)[1].strip()
                        prerequisites = [p.strip() for p in prereq_text.split(",")]

        logger.debug(f"Final skill name: '{skill_name}'")
        logger.debug(f"Description: '{description}'")
        logger.debug(f"Category: {category}")
        logger.debug(f"Tags: {tags}")

        return Skill(
            name=skill_name,
            description=description,
            category=category,
            file_path=file_path,
            content=content,
            prerequisites=prerequisites,
            tags=tags,
            difficulty=difficulty,
        )

    def _list_skills(self, limit: int = 5) -> Dict[str, Any]:
        """List available skills."""
        skills_list = list(self.skills.values())

        # Sort by name
        skills_list.sort(key=lambda s: s.name)

        if limit > 0:
            skills_list = skills_list[:limit]

        return create_success_response(
            {
                "skills": [skill.to_dict() for skill in skills_list],
                "total": len(self.skills),
                "shown": len(skills_list),
            }
        )

    def _load_skill(self, skill_name: str) -> Dict[str, Any]:
        """Load a specific skill by name."""
        # Try exact match first
        skill = self.skills.get(skill_name)

        # Try case-insensitive match
        if not skill:
            for name, sk in self.skills.items():
                if name.lower() == skill_name.lower():
                    skill = sk
                    break

        # Try partial match
        if not skill:
            for name, sk in self.skills.items():
                if skill_name.lower() in name.lower():
                    skill = sk
                    break

        if not skill:
            return create_error_response(
                f"Skill not found: {skill_name}",
                ErrorType.NOT_FOUND,
                {"available_skills": list(self.skills.keys())},
            )

        return create_success_response(
            {
                "skill": skill.to_dict(),
                "workflow_steps": skill.get_workflow_steps(),
                "tool_patterns": skill.get_tool_patterns(),
            }
        )

    def _get_skill(self, skill_name: str) -> Dict[str, Any]:
        """Get skill content and metadata."""
        return self._load_skill(skill_name)

    def _suggest_skills(self, task_description: str, limit: int = 5) -> Dict[str, Any]:
        """Suggest skills applicable to a task."""
        scored_skills = []

        for skill in self.skills.values():
            score = skill.is_applicable(task_description)
            if score > 0:
                scored_skills.append((score, skill))

        # Sort by score descending
        scored_skills.sort(key=lambda x: x[0], reverse=True)

        if limit > 0:
            scored_skills = scored_skills[:limit]

        suggestions = []
        for score, skill in scored_skills:
            skill_dict = skill.to_dict()
            skill_dict["applicability_score"] = score
            suggestions.append(skill_dict)

        return create_success_response(
            {
                "suggestions": suggestions,
                "task": task_description,
                "total_considered": len(self.skills),
            }
        )

    def detect_applicable(
        self,
        task_description: str,
        context: Optional[Dict[str, Any]] = None,
        threshold: float = 0.3,
    ) -> List[Skill]:
        """
        Detect skills applicable to a task (internal method).

        Args:
            task_description: Description of the task
            context: Additional context for skill matching
            threshold: Minimum applicability score (0.0 to 1.0)

        Returns:
            List of applicable skills
        """
        if not self.skills_loaded:
            self._load_skills()

        applicable = []
        for skill in self.skills.values():
            score = skill.is_applicable(task_description, context)
            if score >= threshold:
                applicable.append((score, skill))

        # Sort by score
        applicable.sort(key=lambda x: x[0], reverse=True)

        return [skill for _, skill in applicable]
