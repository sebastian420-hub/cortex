"""Agent routing mixin — model switching, routing, delegation."""

import logging
from typing import Dict, Any, Optional

from ..core.providers import ProviderFactory, ProviderError
from ..ui.console import console

logger = logging.getLogger(__name__)


class AgentRoutingMixin:
    """Mixin providing model switching, routing, and delegation methods."""

    def switch_model(self, new_model: str, provider_override: Optional[str] = None, silent: bool = False) -> None:
        """
        Switch to a different model while maintaining conversation history.

        Reinitializes the provider and updates conversation manager's model reference.
        This allows switching between models (e.g., local to cloud) while keeping
        the same conversation context.

        Args:
            new_model: New model name to use
            provider_override: Optional provider override
            silent: If True, suppress the UI output (useful for orchestrated switches)

        Raises:
            ProviderError: If provider initialization fails or API key is missing
        """
        # Skip if same model
        if new_model == self.model:
            return

        old_model = self.model
        old_provider_name = ProviderFactory.get_provider_name(self.model)

        try:
            # Reinitialize provider for new model
            provider_override = provider_override or getattr(self.config, "provider", None)
            new_provider = ProviderFactory.get_provider(new_model, provider_override)

            # Validate API key for cloud providers
            if not new_provider.validate_api_key():
                provider_name = ProviderFactory.get_provider_name(new_model)
                raise ProviderError(
                    f"API key not set for {provider_name} provider. "
                    f"Please set the required environment variable."
                )

            # Update model and provider
            self.model = new_model
            self.provider = new_provider

            # Update conversation manager's model reference for token counting
            self.conversation.update_model(new_model)

            # Notify user of model switch (unless silent mode)
            if not silent:
                new_provider_name = ProviderFactory.get_provider_name(new_model)
                if old_provider_name != new_provider_name:
                    console.print(
                        f"[cyan]Switched model:[/cyan] {old_model} ({old_provider_name}) -> "
                        f"{new_model} ({new_provider_name})"
                    )
                else:
                    console.print(f"[cyan]Switched model:[/cyan] {old_model} -> {new_model}")

        except ProviderError as e:
            # Keep old model on error
            if not silent:
                console.print(f"[red]Failed to switch model:[/red] {e}")
            raise ProviderError(f"Failed to switch model: {e}") from e

    def route_request(self, user_request: str) -> Optional[Any]:
        """
        Route a user request using the intelligent routing system.

        This analyzes the request and determines the optimal model/provider.
        If routing is not enabled, returns None and uses the default model.

        Args:
            user_request: The user's natural language request

        Returns:
            RoutingDecision if routing is enabled, None otherwise
        """
        if not self._routing_enabled or not self.router:
            return None

        try:
            from ..core.routing import RoutingContext

            # Create routing context from current session
            context = RoutingContext(
                session_id=str(id(self)),
                conversation_history=self.conversation.get_history(),
            )

            # Get routing decision
            decision = self.router.route_request(
                user_request,
                context=context,
                force_model=self.model if self.config.provider else None,
            )

            # Display routing decision if in text mode
            if self._is_text_output() and decision:
                self._display_routing_decision(decision)

            return decision

        except Exception as e:
            logger.warning(f"Routing failed, using default model: {e}")
            return None

    def _display_routing_decision(self, decision) -> None:
        """Display routing decision to user."""
        if not self._is_text_output():
            return

        # Compact display
        task_info = ""
        if decision.task_analysis:
            task_info = f" ({decision.task_analysis.task_type.value})"

        cost_info = ""
        if decision.estimated_cost_usd is not None:
            if decision.estimated_cost_usd == 0:
                cost_info = " [free]"
            else:
                cost_info = f" [~${decision.estimated_cost_usd:.4f}]"

        console.print(
            f"[dim]Router:[/dim] {decision.model_name} via {decision.provider_name}"
            f"{task_info}{cost_info}"
        )

    def get_routing_statistics(self) -> Optional[Dict[str, Any]]:
        """
        Get routing system statistics.

        Returns:
            Dictionary of routing statistics, or None if routing is disabled
        """
        if not self._routing_enabled or not self.router:
            return None

        return self.router.get_statistics()

    def _get_orchestration_prompt(self) -> str:
        """Generate orchestration-specific prompt injection for current model."""
        from ..core.prompts import get_delegation_instructions

        # Check if orchestration has been initialized yet
        if not hasattr(self, "_orchestration_enabled") or not self._orchestration_enabled:
            return ""
        if not hasattr(self, "_model_registry") or not self._model_registry:
            return ""

        # Get model config
        model_config = self._model_registry.get_model(self.model)
        if not model_config:
            return ""

        # Get available delegation targets
        available_delegates = self._model_registry.get_delegation_targets(self.model)

        # Get remaining delegations
        remaining = 5  # Default
        if self._delegation_tracker:
            remaining = self._delegation_tracker.get_remaining()

        # Get prompt profile
        profile_name = model_config.prompt_profile
        prompt = get_delegation_instructions(
            current_model=self.model,
            available_delegates=available_delegates,
            remaining_delegations=remaining,
            profile_name=profile_name,
        )

        # Add delegation context if present
        if self._delegation_context:
            prompt = f"{self._delegation_context.to_system_context()}\n\n{prompt}"

        return prompt

    def _handle_delegation_action(self, result: Dict[str, Any]) -> bool:
        """
        Handle a delegation action from a tool result.

        Args:
            result: Tool result containing delegation action

        Returns:
            True if delegation was handled and model switched, False otherwise
        """
        action = result.get("action")

        if action == "delegate":
            target_model = result.get("target_model")
            task = result.get("task", "")
            handoff_notes = result.get("handoff_notes", "")

            if not target_model:
                logger.warning("Delegation action missing target_model")
                return False

            # Prepare delegation context
            if self._orchestration:
                self._delegation_context = self._orchestration.prepare_delegation(
                    to_model=target_model,
                    task=task,
                    handoff_notes=handoff_notes,
                    conversation_history=self.conversation.get_history(),
                    state_summary=self._get_state_summary(),
                )

            # Switch to target model
            try:
                target_config = self._model_registry.get_model(target_model) if self._model_registry else None
                provider_override = target_config.provider if target_config else None
                # Use full API model name if available
                api_model_name = target_config.api_model_name if target_config and target_config.api_model_name else target_model

                self.switch_model(api_model_name, provider_override=provider_override, silent=True)

                # Update system prompt with new model's profile
                new_prompt = self._get_system_prompt()
                self.conversation.update_system_prompt(new_prompt)

                if self._is_text_output():
                    console.print(
                        f"[cyan]Delegated:[/cyan] {result.get('from_model')} -> {target_model}\n"
                        f"[dim]Task: {task[:80]}...[/dim]"
                    )

                return True

            except ProviderError as e:
                logger.error(f"Failed to switch model for delegation: {e}")
                if self._is_text_output():
                    console.print(f"[red]Delegation failed:[/red] {e}")
                return False

        elif action == "return_to_coordinator":
            coordinator = result.get("target_model", "mimo-v2-flash")
            summary = result.get("summary", "")

            # Clear delegation context
            self._delegation_context = None

            # Switch back to coordinator
            try:
                coordinator_config = self._model_registry.get_model(coordinator) if self._model_registry else None
                provider_override = coordinator_config.provider if coordinator_config else None
                # Use full API model name if available
                api_model_name = coordinator_config.api_model_name if coordinator_config and coordinator_config.api_model_name else coordinator

                self.switch_model(api_model_name, provider_override=provider_override, silent=True)

                # Update system prompt
                new_prompt = self._get_system_prompt()
                self.conversation.update_system_prompt(new_prompt)

                if self._is_text_output():
                    console.print(
                        f"[cyan]Returned to coordinator:[/cyan] {coordinator}\n"
                        f"[dim]Summary: {summary[:80]}...[/dim]"
                    )

                return True

            except ProviderError as e:
                logger.error(f"Failed to return to coordinator: {e}")
                return False

        return False
