"""Hook manager for registering and dispatching hooks"""

from typing import List, Dict, Any, Optional, Type
import logging

from .base import BaseHook, HookEvent, HookResult, HookAction

logger = logging.getLogger(__name__)


class HookManager:
    """
    Manages hook registration and event dispatch.

    The HookManager is responsible for:
    - Registering and unregistering hooks
    - Dispatching events to appropriate hooks
    - Managing hook execution order by priority
    - Handling hook results and action chains
    """

    def __init__(self):
        """Initialize an empty hook manager."""
        self._hooks: List[BaseHook] = []
        self._enabled = True

    def register(self, hook: BaseHook) -> None:
        """
        Register a hook.

        Hooks are stored sorted by priority (lower priority = earlier execution).

        Args:
            hook: The hook to register
        """
        if hook not in self._hooks:
            self._hooks.append(hook)
            # Sort by priority
            self._hooks.sort(key=lambda h: h.priority)
            logger.debug(f"Registered hook: {hook.name} (priority={hook.priority})")

    def unregister(self, hook: BaseHook) -> bool:
        """
        Unregister a hook.

        Args:
            hook: The hook to unregister

        Returns:
            True if hook was found and removed, False otherwise
        """
        if hook in self._hooks:
            self._hooks.remove(hook)
            logger.debug(f"Unregistered hook: {hook.name}")
            return True
        return False

    def unregister_by_name(self, name: str) -> int:
        """
        Unregister all hooks with a given name.

        Args:
            name: Hook name to unregister

        Returns:
            Number of hooks removed
        """
        to_remove = [h for h in self._hooks if h.name == name]
        for hook in to_remove:
            self._hooks.remove(hook)
        return len(to_remove)

    def dispatch(self, event: HookEvent) -> HookResult:
        """
        Dispatch an event to all relevant hooks.

        Hooks are executed in priority order. The dispatch stops if:
        - A hook returns ABORT (entire operation is aborted)
        - A hook returns SKIP (operation is skipped)

        If a hook returns MODIFY, the modified data is passed to subsequent hooks.

        Args:
            event: The event to dispatch

        Returns:
            Combined HookResult from all hook executions
        """
        if not self._enabled:
            return HookResult.continue_execution()

        current_data = event.data.copy()
        final_result = HookResult.continue_execution()

        for hook in self._hooks:
            if not hook.should_handle(event.event_type):
                continue

            try:
                # Update event with potentially modified data
                event.data = current_data

                # Execute hook
                result = hook.execute(event)

                logger.debug(f"Hook {hook.name} returned: {result.action.value}")

                # Handle actions
                if result.action == HookAction.ABORT:
                    logger.info(f"Hook {hook.name} aborted: {result.message}")
                    return result

                elif result.action == HookAction.SKIP:
                    logger.info(f"Hook {hook.name} skipped: {result.message}")
                    return result

                elif result.action == HookAction.MODIFY:
                    if result.modified_data:
                        current_data = result.modified_data
                        final_result = HookResult.modify_data(
                            current_data,
                            result.message
                        )
                        logger.debug(f"Hook {hook.name} modified data")

            except Exception as e:
                logger.error(f"Hook {hook.name} raised exception: {e}")
                # Continue with other hooks on exception
                continue

        # Update final result with accumulated modifications
        if final_result.action == HookAction.MODIFY:
            final_result.modified_data = current_data

        return final_result

    def dispatch_all(self, event: HookEvent) -> List[HookResult]:
        """
        Dispatch an event to all hooks and collect all results.

        Unlike dispatch(), this method does not stop on ABORT or SKIP,
        and returns results from all hooks.

        Args:
            event: The event to dispatch

        Returns:
            List of HookResults from all hooks
        """
        if not self._enabled:
            return []

        results = []
        for hook in self._hooks:
            if not hook.should_handle(event.event_type):
                continue

            try:
                result = hook.execute(event)
                results.append(result)
            except Exception as e:
                logger.error(f"Hook {hook.name} raised exception: {e}")
                results.append(HookResult.abort_operation(str(e)))

        return results

    def enable(self) -> None:
        """Enable the hook manager (hooks will be executed)."""
        self._enabled = True
        logger.debug("HookManager enabled")

    def disable(self) -> None:
        """Disable the hook manager (hooks will not be executed)."""
        self._enabled = False
        logger.debug("HookManager disabled")

    @property
    def is_enabled(self) -> bool:
        """Check if the hook manager is enabled."""
        return self._enabled

    def list_hooks(self, event_type: Optional[str] = None) -> List[BaseHook]:
        """
        List registered hooks.

        Args:
            event_type: Optional filter by event type

        Returns:
            List of hooks matching the filter
        """
        if event_type:
            return [h for h in self._hooks if h.should_handle(event_type)]
        return list(self._hooks)

    def clear(self) -> None:
        """Remove all registered hooks."""
        self._hooks.clear()
        logger.debug("Cleared all hooks")

    def get_hook(self, name: str) -> Optional[BaseHook]:
        """
        Get a hook by name.

        Args:
            name: Hook name to find

        Returns:
            First hook with matching name, or None
        """
        for hook in self._hooks:
            if hook.name == name:
                return hook
        return None

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "HookManager":
        """
        Create a HookManager from configuration.

        Config format:
        {
            "hooks": [
                {
                    "type": "logging",
                    "enabled": true,
                    "config": {...}
                },
                {
                    "type": "permission",
                    "config": {
                        "require_approval": ["write_file"]
                    }
                }
            ]
        }

        Args:
            config: Configuration dictionary

        Returns:
            Configured HookManager instance
        """
        manager = cls()

        hooks_config = config.get("hooks", [])
        for hook_config in hooks_config:
            hook = cls._create_hook_from_config(hook_config)
            if hook:
                manager.register(hook)

        return manager

    @classmethod
    def _create_hook_from_config(cls, hook_config: Dict[str, Any]) -> Optional[BaseHook]:
        """
        Create a hook instance from configuration.

        Args:
            hook_config: Hook configuration dictionary

        Returns:
            Hook instance, or None if creation failed
        """
        hook_type = hook_config.get("type")
        if not hook_type:
            logger.warning("Hook config missing 'type' field")
            return None

        # Import built-in hooks
        from .builtin import LoggingHook, PermissionHook, CommandBlockerHook

        # Map type names to classes
        hook_classes: Dict[str, Type[BaseHook]] = {
            "logging": LoggingHook,
            "permission": PermissionHook,
            "command_blocker": CommandBlockerHook,
        }

        hook_class = hook_classes.get(hook_type)
        if not hook_class:
            logger.warning(f"Unknown hook type: {hook_type}")
            return None

        try:
            hook_params = hook_config.get("config", {})
            enabled = hook_config.get("enabled", True)

            hook = hook_class(**hook_params)
            hook.enabled = enabled

            return hook

        except Exception as e:
            logger.error(f"Failed to create hook {hook_type}: {e}")
            return None

    def __len__(self) -> int:
        """Return number of registered hooks."""
        return len(self._hooks)

    def __repr__(self) -> str:
        return f"HookManager(hooks={len(self._hooks)}, enabled={self._enabled})"
