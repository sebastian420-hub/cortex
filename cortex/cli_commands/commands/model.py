"""Model commands - model switching and information"""

from typing import Optional
import logging
from rich.table import Table

from .base import Command, CommandContext
from ...ui.console import console
from ...core.model_capabilities import get_model_profile
from ...core.prompts import get_adapter_info
from ...core.providers import ProviderError

logger = logging.getLogger(__name__)


class ModelCommand(Command):
    """Switch or display current model"""

    @property
    def name(self) -> str:
        return "model"

    @property
    def description(self) -> str:
        return "Switch or display current model"

    def execute(self, ctx: CommandContext, args: Optional[str] = None) -> None:
        """Execute the model command"""
        logger.debug(f"ModelCommand.execute called with args='{args}'")

        if args:
            new_model = args.strip()
            logger.debug(f"Calling agent.switch_model with model='{new_model}'")
            try:
                ctx.agent.switch_model(new_model, ctx.agent.config.provider)
                console.print(f"[green]✓[/green] Model switched to: {ctx.agent.model}")
                # Update system prompt in case it contains model-specific instructions
                ctx.agent.conversation.history[0]["content"] = ctx.agent._get_system_prompt()
            except ProviderError as e:
                console.print(f"[red]Error switching model:[/red] {e}")
            except Exception as e:
                console.print(f"[red]An unexpected error occurred:[/red] {e}")
        else:
            console.print(f"Current model: {ctx.agent.model}")
            console.print("[dim]Usage: /model <model_name>[/dim]")


class ProfileCommand(Command):
    """Show model capability profile"""

    @property
    def name(self) -> str:
        return "profile"

    @property
    def description(self) -> str:
        return "Show model capability profile"

    def execute(self, ctx: CommandContext, args: Optional[str] = None) -> None:
        """Execute the profile command"""
        model_to_check = args.strip() if args else ctx.agent.model

        profile = get_model_profile(model_to_check)
        adapter_info = get_adapter_info(model_to_check)

        # Create a table for the profile
        table = Table(
            title=f"Model Profile: {profile.name}", show_header=True, header_style="bold cyan"
        )
        table.add_column("Property", style="dim")
        table.add_column("Value")

        table.add_row("Model", model_to_check)
        table.add_row("Profile Name", profile.name)
        table.add_row("Context Window", f"{profile.context_window:,} tokens")
        table.add_row("Prompt Style", profile.prompt_style.value)
        table.add_row("Tool Following", profile.tool_following.value)
        table.add_row("Reasoning", profile.reasoning.value)
        table.add_row("Max Tools", str(profile.max_tools_per_prompt))
        table.add_row("JSON Mode", "Yes" if profile.supports_json_mode else "No")
        table.add_row("Streaming", "Yes" if profile.supports_streaming else "No")
        table.add_row("Vision", "Yes" if profile.supports_vision else "No")
        table.add_row("Adapter", adapter_info.get("adapter", "none"))
        if profile.notes:
            table.add_row("Notes", profile.notes)

        console.print(table)
        console.print("\n[dim]Usage: /profile [model_name] - Check any model's profile[/dim]")
