"""What each tool is allowed to do, in one place.

PLAN mode promises that nothing in the project changes and no project code runs. That promise
used to depend on every tool remembering to check the mode itself, and on a hand-written list of
"destructive" tool names that had drifted from the real names (it listed ``edit_file``; the tool
is ``edit``). Here every tool is classified once, and PLAN mode is an allowlist: a tool that is
not known to be harmless is refused, so a newly added tool is blocked until someone classifies it.
"""

from enum import Enum
from typing import Any, Dict, Optional


class ToolClass(str, Enum):
    READ_ONLY = "read_only"  # reads the project or the web; changes nothing
    AGENT_STATE = "agent_state"  # changes only the agent's own bookkeeping (todos, plans, memory)
    MUTATING = "mutating"  # writes files, the git index/history, or a remote
    RUNS_CODE = "runs_code"  # executes commands or project code (tests, shell)


_CLASSES: Dict[str, ToolClass] = {
    # Reads
    "read_file": ToolClass.READ_ONLY,
    "list_files": ToolClass.READ_ONLY,
    "search_files": ToolClass.READ_ONLY,
    "grep": ToolClass.READ_ONLY,
    "glob": ToolClass.READ_ONLY,
    "git_status": ToolClass.READ_ONLY,
    "git_diff": ToolClass.READ_ONLY,
    "git_log": ToolClass.READ_ONLY,
    "git_remote": ToolClass.READ_ONLY,
    "git_show": ToolClass.READ_ONLY,
    "web_fetch": ToolClass.READ_ONLY,
    "web_search": ToolClass.READ_ONLY,
    "ast_search": ToolClass.READ_ONLY,
    "ast_extract": ToolClass.READ_ONLY,
    "ast_analyze": ToolClass.READ_ONLY,
    "ask_user_question": ToolClass.READ_ONLY,
    # Agent bookkeeping. Plan steps still reach the project only through the tools above and
    # below, each of which is checked on its own.
    "skill_loader": ToolClass.AGENT_STATE,
    "todo_write": ToolClass.AGENT_STATE,
    "monitor_plan": ToolClass.AGENT_STATE,
    "update_plan": ToolClass.AGENT_STATE,
    "create_and_execute_plan": ToolClass.AGENT_STATE,
    "metacognitive_reflect": ToolClass.AGENT_STATE,
    "remember": ToolClass.AGENT_STATE,
    "delegate_to_model": ToolClass.AGENT_STATE,
    "return_to_coordinator": ToolClass.AGENT_STATE,
    # Writes
    "write_file": ToolClass.MUTATING,
    "edit": ToolClass.MUTATING,
    "ast_refactor": ToolClass.MUTATING,
    "git_add": ToolClass.MUTATING,
    "git_commit": ToolClass.MUTATING,
    "git_branch": ToolClass.MUTATING,  # "list" is refined to READ_ONLY in classify_tool
    "git_checkout": ToolClass.MUTATING,
    "git_reset": ToolClass.MUTATING,
    "git_fetch": ToolClass.MUTATING,
    "git_pull": ToolClass.MUTATING,
    "git_push": ToolClass.MUTATING,
    # Runs code
    "execute_command": ToolClass.RUNS_CODE,
    "run_tests": ToolClass.RUNS_CODE,
}

# Classes PLAN mode lets through
PLAN_MODE_CLASSES = frozenset({ToolClass.READ_ONLY, ToolClass.AGENT_STATE})


def classify_tool(name: str, args: Optional[Dict[str, Any]] = None) -> Optional[ToolClass]:
    """The class of a tool, or None when it has not been classified.

    A few tools do different things depending on an argument; pass ``args`` to refine those.
    """
    tool_class = _CLASSES.get(name)
    if name == "git_branch" and args is not None and args.get("action", "list") == "list":
        return ToolClass.READ_ONLY
    return tool_class


def allowed_in_plan_mode(name: str, args: Optional[Dict[str, Any]] = None) -> bool:
    """True when PLAN mode may run this tool. Unclassified tools are refused."""
    return classify_tool(name, args) in PLAN_MODE_CLASSES
