"""PLAN mode is an allowlist built from a single classification of every tool."""

from unittest.mock import MagicMock

import pytest

from cortex.core.agent_permissions import PermissionManager
from cortex.core.tool_policy import ToolClass, allowed_in_plan_mode, classify_tool
from cortex.models import PermissionMode
from cortex.tools import get_registry


def _registered_names():
    return [s["function"]["name"] for s in get_registry().get_all_schemas()]


def _plan_manager():
    agent = MagicMock()
    agent.permission_mode = PermissionMode.PLAN
    return PermissionManager(agent)


@pytest.mark.parametrize("name", _registered_names())
def test_every_registered_tool_is_classified(name):
    assert isinstance(classify_tool(name), ToolClass)


@pytest.mark.parametrize(
    "name", ["write_file", "edit", "ast_refactor", "git_commit", "git_push", "git_checkout"]
)
def test_mutating_tools_are_refused_in_plan_mode(name):
    assert classify_tool(name) is ToolClass.MUTATING
    assert _plan_manager().check(name, {}) is False


@pytest.mark.parametrize("name", ["execute_command", "run_tests"])
def test_tools_that_run_code_are_refused_in_plan_mode(name):
    assert classify_tool(name) is ToolClass.RUNS_CODE
    assert _plan_manager().check(name, {}) is False


@pytest.mark.parametrize("name", ["read_file", "grep", "glob", "git_diff", "ast_analyze"])
def test_read_only_tools_work_in_plan_mode(name):
    assert _plan_manager().check(name, {}) is True


def test_a_tool_nobody_classified_is_refused_in_plan_mode():
    assert classify_tool("brand_new_tool") is None
    assert allowed_in_plan_mode("brand_new_tool") is False
    assert _plan_manager().check("brand_new_tool", {}) is False


def test_git_branch_is_read_only_only_when_listing():
    assert allowed_in_plan_mode("git_branch", {"action": "list"}) is True
    assert allowed_in_plan_mode("git_branch", {}) is True  # the tool's default action is "list"
    assert allowed_in_plan_mode("git_branch", {"action": "create"}) is False
    assert allowed_in_plan_mode("git_branch", {"action": "delete"}) is False


def test_the_policy_does_not_affect_other_modes():
    agent = MagicMock()
    agent.permission_mode = PermissionMode.AUTO_APPROVE
    assert PermissionManager(agent).check("write_file", {"path": "x"}) is True
