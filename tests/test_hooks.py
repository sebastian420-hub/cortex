"""Tests for Hook System"""

import pytest

from cortex.hooks import (
    HookAction,
    HookEvent,
    HookResult,
    BaseHook,
    HookManager,
    PreToolUseEvent,
    PostToolUseEvent,
    LoggingHook,
    PermissionHook,
    CommandBlockerHook,
)


class AllowHook(BaseHook):
    """Hook that allows everything"""

    handles = ["*"]
    name = "AllowHook"

    def execute(self, event: HookEvent) -> HookResult:
        return HookResult.continue_execution()


class BlockHook(BaseHook):
    """Hook that blocks everything"""

    handles = ["*"]
    name = "BlockHook"

    def execute(self, event: HookEvent) -> HookResult:
        return HookResult.abort_operation("Blocked by test hook")


class ModifyHook(BaseHook):
    """Hook that modifies data"""

    handles = ["pre_tool_use"]
    name = "ModifyHook"

    def execute(self, event: HookEvent) -> HookResult:
        modified = event.data.copy()
        modified["arguments"]["modified"] = True
        return HookResult.modify_data(modified)


class CountingHook(BaseHook):
    """Hook that counts invocations"""

    handles = ["*"]
    name = "CountingHook"

    def __init__(self):
        super().__init__()
        self.count = 0

    def execute(self, event: HookEvent) -> HookResult:
        self.count += 1
        return HookResult.continue_execution()


class TestHookEvent:
    """Test HookEvent class"""

    def test_create_event(self):
        """Test creating a hook event"""
        event = HookEvent(event_type="test_event", data={"key": "value"}, context={"ctx": "data"})

        assert event.event_type == "test_event"
        assert event.data["key"] == "value"
        assert event.context["ctx"] == "data"

    def test_event_get(self):
        """Test event get method"""
        event = HookEvent(event_type="test", data={"key": "value"})

        assert event.get("key") == "value"
        assert event.get("missing") is None
        assert event.get("missing", "default") == "default"

    def test_event_getitem(self):
        """Test dict-like access"""
        event = HookEvent(event_type="test", data={"key": "value"})

        assert event["key"] == "value"


class TestHookResult:
    """Test HookResult class"""

    def test_continue_execution(self):
        """Test continue execution result"""
        result = HookResult.continue_execution()
        assert result.action == HookAction.CONTINUE
        assert result.modified_data is None

    def test_skip_operation(self):
        """Test skip operation result"""
        result = HookResult.skip_operation("Skipping test")
        assert result.action == HookAction.SKIP
        assert result.message == "Skipping test"

    def test_modify_data(self):
        """Test modify data result"""
        data = {"key": "modified_value"}
        result = HookResult.modify_data(data, "Modified data")

        assert result.action == HookAction.MODIFY
        assert result.modified_data == data
        assert result.message == "Modified data"

    def test_abort_operation(self):
        """Test abort operation result"""
        result = HookResult.abort_operation("Test abort")
        assert result.action == HookAction.ABORT
        assert result.message == "Test abort"


class TestBaseHook:
    """Test BaseHook class"""

    def test_should_handle(self):
        """Test should_handle method"""
        hook = AllowHook()
        assert hook.should_handle("pre_tool_use") is True
        assert hook.should_handle("any_event") is True

    def test_should_handle_specific(self):
        """Test specific event handling"""
        hook = ModifyHook()
        assert hook.should_handle("pre_tool_use") is True
        assert hook.should_handle("post_tool_use") is False

    def test_enable_disable(self):
        """Test enabling and disabling hooks"""
        hook = AllowHook()
        assert hook.enabled is True

        hook.disable()
        assert hook.enabled is False
        assert hook.should_handle("any") is False

        hook.enable()
        assert hook.enabled is True
        assert hook.should_handle("any") is True


class TestHookManager:
    """Test HookManager class"""

    def test_register_hook(self):
        """Test registering hooks"""
        manager = HookManager()
        hook = AllowHook()

        manager.register(hook)

        assert len(manager) == 1
        assert hook in manager.list_hooks()

    def test_unregister_hook(self):
        """Test unregistering hooks"""
        manager = HookManager()
        hook = AllowHook()

        manager.register(hook)
        assert manager.unregister(hook) is True
        assert len(manager) == 0

    def test_dispatch_continue(self):
        """Test dispatching with continue result"""
        manager = HookManager()
        manager.register(AllowHook())

        event = HookEvent(event_type="test", data={"key": "value"})
        result = manager.dispatch(event)

        assert result.action == HookAction.CONTINUE

    def test_dispatch_abort(self):
        """Test dispatching with abort result"""
        manager = HookManager()
        manager.register(BlockHook())

        event = HookEvent(event_type="test", data={"key": "value"})
        result = manager.dispatch(event)

        assert result.action == HookAction.ABORT
        assert result.message == "Blocked by test hook"

    def test_dispatch_modify(self):
        """Test dispatching with modify result"""
        manager = HookManager()
        manager.register(ModifyHook())

        event = PreToolUseEvent(
            tool_name="test_tool", arguments={"arg": "value"}, permission_mode="normal"
        )
        result = manager.dispatch(event)

        assert result.action == HookAction.MODIFY
        assert result.modified_data["arguments"]["modified"] is True

    def test_priority_order(self):
        """Test hooks execute in priority order"""
        manager = HookManager()

        hook1 = CountingHook()
        hook1.priority = 100
        hook2 = CountingHook()
        hook2.priority = 50

        manager.register(hook1)
        manager.register(hook2)

        # hook2 should be first (lower priority)
        hooks = manager.list_hooks()
        assert hooks[0].priority == 50
        assert hooks[1].priority == 100

    def test_disabled_manager(self):
        """Test disabled hook manager"""
        manager = HookManager()
        manager.register(BlockHook())
        manager.disable()

        event = HookEvent(event_type="test", data={})
        result = manager.dispatch(event)

        # Should continue even though BlockHook would abort
        assert result.action == HookAction.CONTINUE

    def test_clear_hooks(self):
        """Test clearing all hooks"""
        manager = HookManager()
        manager.register(AllowHook())
        manager.register(BlockHook())

        manager.clear()
        assert len(manager) == 0

    def test_get_hook_by_name(self):
        """Test getting hook by name"""
        manager = HookManager()
        hook = AllowHook()
        manager.register(hook)

        found = manager.get_hook("AllowHook")
        assert found is hook
        assert manager.get_hook("NonexistentHook") is None


class TestPreToolUseEvent:
    """Test PreToolUseEvent class"""

    def test_create_event(self):
        """Test creating pre tool use event"""
        event = PreToolUseEvent(
            tool_name="read_file", arguments={"path": "test.txt"}, permission_mode="normal"
        )

        assert event.event_type == "pre_tool_use"
        assert event.tool_name == "read_file"
        assert event.arguments == {"path": "test.txt"}
        assert event.permission_mode == "normal"


class TestPostToolUseEvent:
    """Test PostToolUseEvent class"""

    def test_create_event(self):
        """Test creating post tool use event"""
        event = PostToolUseEvent(
            tool_name="read_file",
            arguments={"path": "test.txt"},
            result={"success": True, "content": "test"},
            success=True,
            duration_ms=100.5,
        )

        assert event.event_type == "post_tool_use"
        assert event.tool_name == "read_file"
        assert event.success is True
        assert event.duration_ms == 100.5


class TestBuiltinHooks:
    """Test built-in hook implementations"""

    def test_logging_hook(self):
        """Test logging hook"""
        hook = LoggingHook()

        event = PreToolUseEvent(tool_name="test", arguments={}, permission_mode="normal")
        result = hook.execute(event)

        # Logging hook should always continue
        assert result.action == HookAction.CONTINUE

    def test_permission_hook_allowed(self):
        """Test permission hook allows tools"""
        hook = PermissionHook(allowed=["read_file", "list_files"])

        event = PreToolUseEvent(tool_name="read_file", arguments={}, permission_mode="normal")
        result = hook.execute(event)

        assert result.action == HookAction.CONTINUE

    def test_permission_hook_blocked(self):
        """Test permission hook blocks tools"""
        hook = PermissionHook(blocked=["execute_command"])

        event = PreToolUseEvent(tool_name="execute_command", arguments={}, permission_mode="normal")
        result = hook.execute(event)

        assert result.action == HookAction.ABORT

    def test_permission_hook_whitelist(self):
        """Test permission hook whitelist mode"""
        hook = PermissionHook(allowed=["read_file"])  # Only read_file allowed

        # Allowed tool
        event1 = PreToolUseEvent(tool_name="read_file", arguments={}, permission_mode="normal")
        assert hook.execute(event1).action == HookAction.CONTINUE

        # Not in allowed list
        event2 = PreToolUseEvent(tool_name="write_file", arguments={}, permission_mode="normal")
        assert hook.execute(event2).action == HookAction.ABORT

    def test_command_blocker_hook(self):
        """Test command blocker hook"""
        hook = CommandBlockerHook()

        # Safe command
        safe_event = PreToolUseEvent(
            tool_name="execute_command", arguments={"command": "ls -la"}, permission_mode="normal"
        )
        assert hook.execute(safe_event).action == HookAction.CONTINUE

        # Dangerous command
        dangerous_event = PreToolUseEvent(
            tool_name="execute_command", arguments={"command": "rm -rf /"}, permission_mode="normal"
        )
        assert hook.execute(dangerous_event).action == HookAction.ABORT

    def test_command_blocker_non_command_tool(self):
        """Test command blocker ignores non-command tools"""
        hook = CommandBlockerHook()

        event = PreToolUseEvent(
            tool_name="read_file",
            arguments={"path": "rm -rf /"},  # Even with dangerous content
            permission_mode="normal",
        )
        result = hook.execute(event)

        # Should continue because it's not execute_command
        assert result.action == HookAction.CONTINUE
