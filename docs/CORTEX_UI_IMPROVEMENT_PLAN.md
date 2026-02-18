# Cortex UI Improvement Plan - Minimal Mode Like Claude Code

## Goal
Create a toggleable UI system with **Minimal Mode** (Claude Code style), **Normal Mode** (current Cortex), and **Debug Mode** (development details).

## Understanding the Current UI

### Current Structure
1. **cortex/ui/display.py** - Rich display functions with panels
2. **cortex/ui/repl.py** - REPL with basic key bindings
3. **cortex/ui/console.py** - Global console instance
4. **cortex/ui/progress.py** - Progress indicators
5. **cortex/ui/plan_progress.py** - Plan progress display

### Current Display Patterns
- **File diffs**: `Panel(diff_text, title=f"📊 Diff: {path}", border_style="yellow")`
- **File previews**: `Panel(syntax, title=f"📄 {path}", border_style="cyan")`
- **Thinking displays**: `Panel(content, title="[bold yellow]💭 Thinking[/bold yellow]", border_style="yellow")`
- **Operation completion**: Simple line `"[green]✓[/green] Operation - summary (0.5s)"`

## The Problem
The current UI uses **rich panels everywhere**, which creates visual clutter. Claude Code uses a **minimal, clean approach**:
- No panels/borders
- Simple icons (⚙️, 💭, 📋)
- One-line summaries
- Timing info in parentheses

## Solution: 3 UI Modes

### 1. **Minimal Mode** (Default - Claude Code Style)
- **No panels/borders**
- **Simple icons**: ⚙️ for tools, 💭 for thinking, ✓/✗ for results
- **One-line tool calls**: `[dim]⚙️ read_file (0.02s)[/dim]`
- **Collapsed thinking**: `[dim]💭 Analyzing the code structure...[/dim]`
- **No syntax highlighting panels** - just code blocks
- **Clean, focused output**

### 2. **Normal Mode** (Current Cortex - Rich)
- **Panels for file diffs/previews**
- **Thinking in panels**
- **Progress bars**
- **Syntax highlighted code in panels**
- **Current behavior preserved**

### 3. **Debug Mode** (Development)
- **All details**: Tool args, full results, timings
- **Internal state info**
- **Performance metrics**
- **Useful for debugging agent behavior**

## Implementation Plan

### Phase 1: Core UI Mode System

#### 1.1 Create `cortex/ui/modes.py`
```python
class UIMode(Enum):
    MINIMAL = "minimal"   # Claude Code style
    NORMAL = "normal"     # Current Cortex
    DEBUG = "debug"       # Development details

class UIManager:
    # Singleton managing UI mode
    # Methods: set_mode(), toggle_mode(), should_show_panels(), etc.
```

#### 1.2 Update `cortex/ui/display.py`
Add mode-aware display functions:
```python
def display_thinking_minimal(content: str) -> None:
    """Minimal thinking display"""
    lines = content.split("\n")
    first_line = lines[0].strip() if lines else ""
    if len(first_line) > 80:
        preview = first_line[:80] + "..."
    else:
        preview = first_line
    if preview:
        console.print(f"[dim]💭 {preview}[/dim]")

def display_thinking_normal(content: str) -> None:
    """Current thinking display with panel"""
    console.print(Panel(content, title="[bold yellow]💭 Thinking[/bold yellow]", ...))

def display_thinking(content: str) -> None:
    """Mode-aware thinking display"""
    mode = ui_manager.get_mode()
    if mode == UIMode.MINIMAL:
        display_thinking_minimal(content)
    else:
        display_thinking_normal(content)
```

#### 1.3 Update `cortex/ui/repl.py`
Add keyboard shortcuts:
- `Ctrl+T` - Toggle UI mode (cycles MINIMAL → NORMAL → DEBUG → MINIMAL)
- `F1` - Show current mode and shortcuts
- `Ctrl+O` - Toggle verbose output (if we want separate from mode)

### Phase 2: Mode-Aware Display Functions

#### 2.1 File Operations
- **Minimal**: `[dim]📄 Reading api.py...[/dim]` → `[dim]✓ Read 150 lines[/dim]`
- **Normal**: `Panel(syntax, title="📄 api.py", ...)`
- **Debug**: `[cyan]📄 Read file: api.py (150 lines, 4.2KB, 0.05s)[/cyan]`

#### 2.2 Tool Execution
- **Minimal**: `[dim]⚙️ edit (0.15s)[/dim]`
- **Normal**: Current tool execution display
- **Debug**: `🔧 Tool: edit (args: {...}, result: {...}, duration: 0.15s)`

#### 2.3 Progress Indicators
- **Minimal**: Simple spinner or `[dim]Processing...[/dim]`
- **Normal**: Current progress bars
- **Debug**: Detailed progress with counts and timing

### Phase 3: Keyboard Shortcuts & Configuration

#### 3.1 Enhanced REPL Key Bindings
```python
# In cortex/ui/repl.py
def _setup_key_bindings(self):
    bindings = KeyBindings()
    
    # Existing
    @bindings.add(Keys.ControlD)
    def exit_handler(event): ...
    
    @bindings.add(Keys.ControlL)  
    def clear_handler(event): ...
    
    # New
    @bindings.add('c-t')  # Ctrl+T
    def toggle_ui_mode(event):
        ui_manager.toggle_mode()
        console.print(f"[dim]UI mode: {ui_manager.get_mode().value}[/dim]")
    
    @bindings.add('f1')
    def show_shortcuts(event):
        self._show_shortcuts_help()
    
    self.key_bindings = bindings
```

#### 3.2 Configuration
```python
# In cortex/config.py
DEFAULT_UI = {
    "mode": "minimal",  # minimal, normal, debug
    "keyboard_shortcuts": {
        "toggle_mode": "ctrl+t",
        "clear_screen": "ctrl+l",
        "exit": "ctrl+d",
        "show_help": "f1",
    },
    "defaults": {
        "show_thinking": True,
        "show_timing": False,
        "syntax_highlighting": True,
    }
}
```

### Phase 4: CLI Integration

#### 4.1 Command Line Options
```bash
# Start in minimal mode (like Claude Code)
cortex --ui-mode minimal

# Start in debug mode
cortex --ui-mode debug

# Toggle modes during session
> /ui minimal
> /ui normal  
> /ui debug
```

#### 4.2 Session Commands
```bash
> /mode minimal     # Alias for /ui minimal
> /mode normal
> /mode debug
> /ui               # Show current UI settings
> /shortcuts        # Show keyboard shortcuts
```

## File Changes Required

### New Files
1. `cortex/ui/modes.py` - UI mode management
2. `cortex/ui/shortcuts.py` - Keyboard shortcuts definitions
3. `cortex/ui/display_minimal.py` - Minimal mode display functions

### Modified Files
1. `cortex/ui/display.py` - Make functions mode-aware
2. `cortex/ui/repl.py` - Add keyboard shortcuts
3. `cortex/ui/__init__.py` - Export new components
4. `cortex/help/content.py` - Add UI mode help
5. `cortex/cli.py` - Add --ui-mode argument
6. `cortex/config.py` - Add UI configuration

## Minimal Mode Examples

### Before (Current Cortex):
```
───────────────────────────────────────────────────────
📄 api.py  
───────────────────────────────────────────────────────
1  from fastapi import FastAPI
2  from typing import Optional
3  # ... 17 more lines
───────────────────────────────────────────────────────

───────────────────────────────────────────────────────
💭 Thinking
───────────────────────────────────────────────────────
I see this is a FastAPI application. The bug appears to 
be on line 42 where there's a null pointer...
───────────────────────────────────────────────────────

───────────────────────────────────────────────────────
🔧 Tool Execution
───────────────────────────────────────────────────────
Tool: edit
Args: {"file_path": "api.py", "old_string": "...", ...}
Result: {"success": true, "changes": 1}
───────────────────────────────────────────────────────
```

### After (Minimal Mode - Claude Code Style):
```
[dim]📄 Reading api.py (20 lines)...[/dim]
[dim]💭 Analyzing the code structure...[/dim]
[dim]⚙️ edit (0.15s)[/dim]
[green]✓ Fixed null pointer exception[/green]
```

### Debug Mode:
```
[cyan]📄 File: api.py (20 lines, 842 bytes, 0.02s)[/cyan]
[cyan]💭 Thinking: I see this is a FastAPI application...[/cyan]
[cyan]🔧 Tool: edit[/cyan]
[cyan]  Args: {"file_path": "api.py", "old_string": "result = None", "new_string": "result = {}"}[/cyan]
[cyan]  Result: {"success": true, "changes": 1, "lines_modified": [42]}[/cyan]
[cyan]  Duration: 0.15s[/cyan]
[green]✓ Fixed null pointer exception (0.17s total)[/green]
```

## Keyboard Shortcuts Reference

### Navigation
- `Ctrl+T` - Toggle UI mode (cycle through minimal/normal/debug)
- `Ctrl+L` - Clear screen
- `Ctrl+D` - Exit Cortex
- `F1` - Show keyboard shortcuts
- `↑/↓` - Command history

### Mode-Specific
- In **MINIMAL**: Focus on clean output, minimal interruptions
- In **NORMAL**: Full rich panels, detailed views
- In **DEBUG**: All internal details for development

## Testing Plan

### Test Cases
1. **Mode Switching**: Ctrl+T cycles through modes correctly
2. **Display Adaptation**: Each mode shows appropriate level of detail
3. **Configuration**: CLI args and config files set initial mode
4. **Backward Compatibility**: Normal mode matches current behavior
5. **Performance**: Minimal mode should be faster (fewer panels)

### Manual Testing
```bash
# Test minimal mode
cortex --ui-mode minimal
> read api.py
> search for "def main"
> create a plan to add logging

# Test debug mode  
cortex --ui-mode debug
> read api.py
> # Should show file stats and timing

# Test mode switching during session
cortex
> /ui minimal
> read api.py
> Ctrl+T  # Switch to normal
> read api.py
> Ctrl+T  # Switch to debug
> read api.py
```

## Timeline

### Week 1: Core Infrastructure
- Create `modes.py` and mode-aware display functions
- Implement basic mode switching
- Update `display.py` for minimal mode

### Week 2: Keyboard Shortcuts & REPL
- Add Ctrl+T and F1 shortcuts
- Enhance REPL key bindings
- Add mode status display

### Week 3: CLI & Configuration
- Add `--ui-mode` CLI argument
- Update configuration system
- Add session commands (`/ui`, `/mode`)

### Week 4: Polish & Testing
- Test all three modes
- Fix edge cases
- Update documentation
- Performance optimization

## Success Criteria

### Primary Goals
1. **Minimal mode looks and feels like Claude Code**
2. **Normal mode preserves current behavior** (no breaking changes)
3. **Debug mode useful for development**
4. **Easy switching between modes** (keyboard shortcut)

### Secondary Goals
1. **Performance improvement** in minimal mode
2. **Cleaner default experience** (start in minimal mode)
3. **Discoverable features** (help, shortcuts)
4. **Configurable** via CLI, config files, in-session

## Open Questions

1. Should **syntax highlighting** be disabled in minimal mode?
2. Should **progress bars** be simplified in minimal mode?
3. Should there be a **"quiet" mode** even more minimal than minimal?
4. Should mode be **per-session** or saved in config?

## Next Steps

1. **Review this plan** for feasibility
2. **Start with `cortex/ui/modes.py`** implementation
3. **Test minimal mode display** with sample outputs
4. **Iterate based on feedback**

---

**Summary**: This plan creates a **Claude Code-inspired minimal UI** while keeping the current rich UI as an option. The toggleable system (Ctrl+T) lets users choose between clean/minimal, detailed/rich, or debug/development views based on their needs.

Cortex UI Improvement Completion Plan

Based on my analysis of the CORTEX_UI_IMPROVEMENT_PLAN.md and the current
codebase, I can see the implementation is about 70% complete. Here's a   
comprehensive plan to finish the remaining work:


                        Current Status Assessment

              ✅ Already Implemented (Core Infrastructure)

 1 cortex/ui/modes.py - Complete with UIMode enum and UIManager singleton
 2 Mode-aware display functions in cortex/ui/display.py:
    • show_file_diff() - minimal vs normal/debug display
    • show_file_preview() - minimal shows 3 lines, normal shows panel    
    • display_thinking() - minimal one-liner previews
 3 Keyboard shortcuts - Ctrl+T toggles UI modes (in cortex/ui/repl.py)   
 4 CLI integration - --ui-mode argument with minimal as default
 5 Session commands - /ui command to switch modes interactively
 6 Tool-level mode awareness - edit_tool.py and file_tools.py use        
   is_minimal_mode()

               🔄 Partially Implemented (Needs Completion)

 1 Progress indicators - cortex/ui/progress.py not mode-aware
 2 Debug mode details - Currently shares same display as normal mode     
 3 Configuration defaults - No UI settings in cortex/config.py
 4 F1 help shortcut - Not implemented (though /help command exists)      

                          ❌ Missing Components

 1 Tool execution display - No mode-aware tool call messages (e.g.,      
   [dim]⚙️ edit (0.15s)[/dim])                                           

 2 Debug mode specifics - No extra timing, tool args, or performance     
   metrics
 3 Progress simplification for minimal mode
 4 F1 shortcut for keyboard help display


                 Completion Plan (Organized by Priority)

       Phase 1: Tool Execution Display & Timing (Highest Priority)       

                1.1 Add Mode-Aware Tool Execution Display

Location: cortex/agent.py (around line 1280 in _output_tool_result)      

                                                                         
 def _output_tool_result(self, tool_name: str, result: Dict[str, Any])   
 -> None:
     """Output a tool result using the appropriate formatter."""
     if not self._is_text_output():
         formatted = self.formatter.format_tool_result(tool_name,        
 result)
         self.formatter.write(formatted)
     else:
         # Text mode - show mode-aware tool execution
         from .ui.modes import is_minimal_mode, is_debug_mode
                                                                         
         if is_minimal_mode():
             # Minimal: ⚙️ tool_name (duration)                          
                                                                         
             duration = result.get('duration_ms', 0)
             if duration > 0:
                 self.console.print(f"[dim]⚙️ {tool_name}                
                                                                         
 ({duration:.2f}s)[/dim]")
             else:
                 self.console.print(f"[dim]⚙️ {tool_name}[/dim]")                                                                                  
         elif is_debug_mode():
             # Debug: detailed tool execution info
             duration = result.get('duration_ms', 0)
             success = result.get('success', False)
             icon = "✓" if success else "✗"
             color = "green" if success else "red"
             self.console.print(f"[{color}][TOOL]
 {tool_name}[/{color}]")
             self.console.print(f"  [dim]Args:
 {json.dumps(result.get('metadata', {}), indent=2)}[/dim]")
             self.console.print(f"  [dim]Duration:
 {duration:.2f}ms[/dim]")
         # Normal mode: tools display their own output (current
 behavior)
                                                                         

            1.2 Update Tool Classes to Return Timing Metadata

Files to modify: All tool classes in cortex/tools/

 • Add duration_ms to return results
 • Capture timing in execute() methods

               Phase 2: Progress Indicator Mode-Awareness

                    2.1 Update cortex/ui/progress.py

                                                                         
 # Add import at top
 from .modes import is_minimal_mode, is_debug_mode
                                                                         
 # Update OperationTracker.operation_complete() method
 def operation_complete(
     self,
     description: str,
     success: bool = True,
     summary: str = "",
     duration: Optional[float] = None,
 ) -> None:
     """Display operation completion with mode awareness."""
                                                                         
     if is_minimal_mode():
         # Minimal mode: simple one-liner
         icon = "[green]✓[/green]" if success else "[red]✗[/red]"        
         parts = [icon, description]
         if duration is not None:
             if duration < 1:
                 parts.append(f"[dim]({duration*1000:.0f}ms)[/dim]")     
             else:
                 parts.append(f"[dim]({duration:.1f}s)[/dim]")
         self.console.print(" ".join(parts))
     elif is_debug_mode():
         # Debug mode: detailed timing and metadata
         # ... detailed implementation
     else:
         # Current implementation for normal mode
         # ... existing code
                                                                         

                  2.2 Update Progress Context Managers

 • Make track_operation(), track_files(), track_search() mode-aware      
 • Simplify spinners for minimal mode

                   Phase 3: Debug Mode Implementation

    3.1 Create Debug Display Functions in cortex/ui/display_debug.py     

                                                                         
 """Debug mode display functions for development details."""
                                                                         
 from rich.console import Console
 from typing import Dict, Any, Optional
 import time
                                                                         
 console = Console()
                                                                         
 def display_tool_call_debug(
     tool_name: str,
     arguments: Dict[str, Any],
     start_time: float,
     result: Optional[Dict[str, Any]] = None
 ) -> None:
     """Display detailed tool call information for debug mode."""        
     duration = (time.time() - start_time) * 1000
                                                                         
     console.print(f"[cyan][DEBUG TOOL] {tool_name}[/cyan]")
     console.print(f"  [dim]Arguments: {json.dumps(arguments,
 indent=2)}[/dim]")
     console.print(f"  [dim]Start time: {start_time}[/dim]")
     console.print(f"  [dim]Duration: {duration:.2f}ms[/dim]")
                                                                         
     if result:
         console.print(f"  [dim]Result success: {result.get('success',   
 False)}[/dim]")
         if 'error' in result:
             console.print(f"  [dim]Error: {result.get('error')}[/dim]") 
                                                                         

            3.2 Add Debug Mode to Existing Display Functions

 • Update show_file_diff() and show_file_preview() in display.py to show 
   file stats (size, lines, read time)
 • Add timing information to all debug displays

                   Phase 4: Configuration & CLI Polish

              4.1 Add UI Configuration to cortex/config.py

                                                                         
 # Add to DEFAULT_UI configuration section
 DEFAULT_UI = {
     "mode": "minimal",  # minimal, normal, debug
     "default_mode": "minimal",  # Startup default
     "keyboard_shortcuts": {
         "toggle_mode": "ctrl+t",
         "clear_screen": "ctrl+l",
         "exit": "ctrl+d",
         "show_help": "f1",
     },
     "features": {
         "show_thinking": True,
         "show_timing": False,
         "syntax_highlighting": True,
         "progress_bars": True,  # Show progress bars in normal/debug    
     }
 }
                                                                         
 # Add to AgentConfig.__init__()
 self.ui_config = ui_config or DEFAULT_UI
                                                                         

                      4.2 Add F1 Keyboard Shortcut

File: cortex/ui/repl.py

                                                                         
 # In _setup_key_bindings() method
 @bindings.add('f1')
 def show_shortcuts_handler(event):
     """F1 to show keyboard shortcuts."""
     from .modes import get_ui_mode
                                                                         
     ui_mode = get_ui_mode()
     shortcuts = {
         "minimal": "Clean, focused output. No panels.",
         "normal": "Rich panels with detailed views.",
         "debug": "Development details and timing.",
     }
                                                                         
     help_text = f"""
 [bold cyan]UI Mode: {ui_mode.value}[/bold cyan]
 {shortcuts.get(ui_mode.value, '')}
                                                                         
 [bold]Keyboard Shortcuts:[/bold]
   Ctrl+T - Toggle UI mode (minimal/normal/debug)
   Ctrl+L - Clear screen
   Ctrl+D - Exit Cortex
   F1     - Show this help
   ↑/↓    - Command history
                                                                         
 [bold]Session Commands:[/bold]
   /ui [mode] - Change UI mode
   /help      - Show all commands
     """
                                                                         
     console.print(Panel(help_text, title="Keyboard Shortcuts"))
                                                                         

                      Phase 5: Testing & Validation

                        5.1 Test Cases to Verify

 1 Mode Switching: Ctrl+T cycles through all three modes correctly       
 2 Display Adaptation: Each mode shows appropriate level of detail       
 3 Tool Execution Display: Tools show mode-appropriate output
 4 Backward Compatibility: Normal mode matches current behavior
 5 Performance: Minimal mode should be faster (fewer Rich panels)        

                        5.2 Manual Testing Script

                                                                         
 # Test minimal mode (default)
 cortex --ui-mode minimal
 > read api.py
 > search for "def main"
 > edit file.py "old" "new"
                                                                         
 # Test debug mode
 cortex --ui-mode debug
 > read api.py  # Should show file stats and timing
 > edit file.py "old" "new"  # Should show tool args and duration        
                                                                         
 # Test mode switching during session
 cortex
 > /ui minimal
 > read api.py
 > Ctrl+T  # Switch to normal
 > read api.py
 > Ctrl+T  # Switch to debug
 > read api.py
 > F1      # Show shortcuts help
                                                                         


                   Implementation Order Recommendation

 1 Start with Phase 1 (Tool execution display) - Highest user impact     
 2 Then Phase 3 (Debug mode) - Completes the 3-mode system
 3 Follow with Phase 2 (Progress indicators) - Improves UX consistency   
 4 Finish with Phase 4 (Configuration & polish) - Final touches
 5 Validate with Phase 5 (Testing) - Ensure quality


                           Estimated Timeline

 • Week 1: Phases 1 & 3 (Core functionality)
 • Week 2: Phase 2 (Progress indicators)
 • Week 3: Phase 4 (Configuration & polish)
 • Week 4: Phase 5 (Testing & bug fixes)


                             Success Metrics

 1 Minimal mode looks and feels like Claude Code (clean, focused)        
 2 Normal mode preserves current behavior (no breaking changes)
 3 Debug mode useful for development (timing, details)
 4 Easy switching between modes (Ctrl+T works flawlessly)
 5 Performance improvement in minimal mode (fewer Rich panels)