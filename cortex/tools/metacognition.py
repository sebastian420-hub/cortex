"""Metacognitive reflection tool for Cortex.

Allows the agent to self-reflect and summarize its experiences into permanent memory.
"""

from typing import Dict, Any, List, Optional
from .base import Tool

REFLECT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "metacognitive_reflect",
        "description": "Summarize the current session or training run into a permanent 'Synthetic Experience'. Use this at the end of a task or training gym to ensure you learn from your successes and failures.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_description": {
                    "type": "string",
                    "description": "Clear description of the problem solved (e.g., 'Fix Circular Import in models.py')"
                },
                "success": {
                    "type": "boolean",
                    "description": "Whether the primary goal was achieved."
                },
                "key_insight": {
                    "type": "string",
                    "description": "The most important engineering lesson learned from this specific task."
                },
                "successful_patterns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of strategies that worked well."
                },
                "failed_attempts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "approach": {"type": "string"},
                            "error": {"type": "string"},
                            "root_cause": {"type": "string"}
                        }
                    },
                    "description": "List of approaches that failed and why."
                },
                "internal_monologue_summary": {
                    "type": "string",
                    "description": "Brief summary of your internal thoughts during the process."
                }
            },
            "required": ["task_description", "success", "key_insight"]
        }
    }
}

class MetacognitiveReflectorTool(Tool):
    """
    Tool for generating 'Synthetic Experiences' for permanent memory.
    """

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        task = kwargs.get("task_description")
        success = kwargs.get("success", False)
        insight = kwargs.get("key_insight")
        
        # In a real implementation, this would trigger the actual save to Vector DB.
        # Currently, the Agent loop catches tool results and the StateManager/MemoryBank 
        # already have logic to extract learnings from tool results.
        
        # We return a structured success message that the EnhancedMemoryBank will see.
        return self._create_success(
            message=f"Metacognitive reflection for '{task}' recorded successfully.",
            synthetic_experience={
                "task": task,
                "success": success,
                "insight": insight,
                "patterns": kwargs.get("successful_patterns", []),
                "failures": kwargs.get("failed_attempts", []),
                "monologue": kwargs.get("internal_monologue_summary", "")
            }
        )
