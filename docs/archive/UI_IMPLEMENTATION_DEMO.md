# Cortex UI Minimal Mode - Simple Implementation

## What You Actually Want (Based on Discussion)

You want the UI to be **cleaner like Claude Code**, not more verbose. The current UI already has details, but it's **too cluttered with panels/borders**.

## Simple Solution: 2 Modes + Keyboard Toggle

### Mode 1: Minimal (Claude Code Style)
- **No panels/borders** - just clean text
- **Simple icons**: ⚙️, 💭, ✓, ✗
- **One-line summaries**
- **Timing in parentheses**

### Mode 2: Normal (Current Cortex)  
- Keep current rich panels
- For backward compatibility

### Mode 3: Debug (Optional)
- For development only

## Minimal Implementation (This Week)

### Step 1: Create Simple Mode Toggle
```python
# cortex/ui/modes.py
class UIMode:
    MINIMAL = "minimal"  # Claude Code style
    NORMAL = "normal"    # Current Cortex
    
    current = NORMAL
    
    @classmethod
    def toggle(cls):
        cls.current = cls.MINIMAL if cls.current == cls.NORMAL else cls.NORMAL
        return cls.current
```

### Step 2: Update display.py Key Functions
```python
# In cortex/ui/display.py
from .modes import UIMode

def display_thinking(content: str, expanded: bool = True) -> None:
    """Mode-aware thinking display"""
    if not content:
        return
    
    content = content.strip()
    
    if UIMode.current == UIMode.MINIMAL and not expanded:
        # Minimal: one line, dim, no panel
        lines = content.split("\n")
        first_line = lines[0].strip() if lines else ""
        if len(first_line) > 80:
            preview = first_line[:80] + "..."
        else:
            preview = first_line
        if preview:
            console.print(f"[dim]💭 {preview}[/dim]")
    elif UIMode.current == UIMode.MINIMAL and expanded:
        # Minimal expanded: still no panel, just indented
        console.print(f"[dim]💭 Thinking:[/dim]")
        for line in content.split("\n"):
            console.print(f"[dim]  {line}[/dim]")
    else:
        # Normal mode: current panel display
        console.print(Panel(content, title="[bold yellow]💭 Thinking[/bold yellow]", ...))

def show_file_preview(content: str, path: str, max_lines: int = 20) -> None:
    """Mode-aware file preview"""
    if UIMode.current == UIMode.MINIMAL:
        # Minimal: just file name and line count
        lines = content.split("\n")
        line_count = len(lines)
        console.print(f"[dim]📄 {path} ({line_count} lines)[/dim]")
        # Show first few lines without panel
        preview_lines = lines[:min(3, max_lines)]
        for line in preview_lines:
            console.print(f"  {line}")
        if line_count > 3:
            console.print(f"[dim]  ... ({line_count - 3} more lines)[/dim]")
    else:
        # Normal: current panel with syntax highlighting
        ext = path.split(".")[-1] if "." in path else "txt"
        syntax = Syntax(content[:500], ext, theme="monokai", line_numbers=True)
        console.print(Panel(syntax, title=f"📄 {path}", border_style="cyan"))
```

### Step 3: Add Keyboard Shortcut to REPL
```python
# In cortex/ui/repl.py, add to _setup_key_bindings:
@bindings.add('c-t')  # Ctrl+T
def toggle_ui_mode(event):
    from .modes import UIMode
    new_mode = UIMode.toggle()
    console.print(f"[dim]UI mode: {new_mode}[/dim]")
```

### Step 4: Add CLI Option
```python
# In cortex/cli.py, add argument:
parser.add_argument("--ui-mode", choices=["minimal", "normal"], default="minimal")
```

## What Changes Visually

### Current Cortex (Normal Mode):
```
───────────────────────────────────────────────
📄 api.py  
───────────────────────────────────────────────
1  from fastapi import FastAPI
2  from typing import Optional
───────────────────────────────────────────────

───────────────────────────────────────────────
💭 Thinking
───────────────────────────────────────────────
I'll analyze this file first...
───────────────────────────────────────────────

[green]✓ Operation complete[/green]
```

### Minimal Mode (Claude Code Style):
```
[dim]📄 api.py (42 lines)[/dim]
  from fastapi import FastAPI
  from typing import Optional
  ...

[dim]💭 I'll analyze this file first...[/dim]

[green]✓ Operation complete[/green]
```

## Even Simpler: Just Remove Panels

Actually, the **simplest solution** is just to remove panels from display functions when in minimal mode:

```python
# Quick fix in display.py
def show_file_preview(content, path, max_lines=20):
    if minimal_mode:  # Some global flag
        # Simple display
        console.print(f"[cyan]📄 {path}[/cyan]")
        console.print(content[:200] + ("..." if len(content) > 200 else ""))
    else:
        # Current panel display
        console.print(Panel(...))
```

## Implementation Priority

### Day 1: Core Mode System
1. Create `cortex/ui/modes.py` (simple class)
2. Update 3 key functions in `display.py`:
   - `display_thinking()`
   - `show_file_preview()`
   - `show_file_diff()`

### Day 2: Keyboard Shortcut
1. Add `Ctrl+T` to REPL
2. Test mode switching

### Day 3: CLI Integration
1. Add `--ui-mode minimal` option
2. Set default to minimal (like Claude Code)

## Testing Commands

```bash
# Start in minimal mode (default)
cortex

# Type Ctrl+T to toggle modes
> Ctrl+T  # Shows "UI mode: normal"
> read api.py  # Shows with panels
> Ctrl+T  # Shows "UI mode: minimal"  
> read api.py  # Shows minimal display

# Or start in specific mode
cortex --ui-mode normal  # Start with panels
cortex --ui-mode minimal # Start clean
```

## Minimal Code Changes

**Only 4 files need changes:**
1. `cortex/ui/modes.py` - NEW (50 lines)
2. `cortex/ui/display.py` - Modify 3 functions (+50 lines)
3. `cortex/ui/repl.py` - Add one key binding (+10 lines)
4. `cortex/cli.py` - Add one argument (+5 lines)

**Total: ~115 lines of code**

## Decision Point

Do you want:
1. **Full 3-mode system** (minimal/normal/debug) - More flexible
2. **Simple toggle** (panels on/off) - Simpler, faster
3. **Just make minimal the default** - Easiest

Given your comment "I just want to minimize it further just like claude code", I recommend **Option 2**: Simple panels on/off toggle with `Ctrl+T`.

This gives you:
- **Minimal mode** by default (like Claude Code)
- **Panels mode** when you need them (Ctrl+T)
- **Simple implementation** (fewer bugs)
- **Quick deployment** (this week)