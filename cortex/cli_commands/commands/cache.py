"""Cache management commands"""

from typing import Optional
from rich.panel import Panel

from .base import Command, CommandContext
from ...ui.console import console


class CacheCommand(Command):
    """Cache management (show stats or clear)"""

    @property
    def name(self) -> str:
        return "cache"

    @property
    def description(self) -> str:
        return "Cache management (show stats or clear)"

    def execute(self, ctx: CommandContext, args: Optional[str] = None) -> None:
        """Execute the cache command"""
        from ...cache import get_file_cache, clear_cache

        cache = get_file_cache(ctx.agent.config.get_file_cache_config())

        if args and args.strip() == "clear":
            clear_cache()
            console.print("[green]✓[/green] File cache cleared")
        else:
            # Show cache stats
            stats = cache.get_stats()
            info = f"""
[bold]File Cache Statistics[/bold]
Enabled: {stats['enabled']}
Entries: {stats['entries']} / {stats['max_entries']}
Size: {stats['size_mb']:.2f} MB / {stats['max_size_mb']:.2f} MB
Hit Rate: {stats['hit_rate']*100:.1f}% ({stats['hits']} hits, {stats['misses']} misses)
"""
            console.print(Panel(info, title="Cache"))
