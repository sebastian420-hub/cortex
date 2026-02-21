# Cortex UI Improvements - Implementation Plan

## Executive Summary

This plan outlines the implementation of UI polish and quality improvements for the Cortex codebase. The goal is to create a more polished, consistent, and professional user interface while maintaining backward compatibility with existing UI modes (minimal/normal/debug).

---

## Phase 1: Foundation (Theme System)

### 1.1 Create Centralized Theme System

**File:** `cortex/ui/theme.py` (NEW)

**Purpose:** Centralize all UI constants (colors, icons, styles) to eliminate inconsistency.

**Implementation:**
```python
class UITheme:
    """Centralized theme configuration for Cortex UI"""
    
    # Color Palette (5 core colors)
    PRIMARY = "bright_cyan"
    SUCCESS = "bright_green"
    WARNING = "bright_yellow"
    ERROR = "bright_red"
    MUTED = "dim"
    
    # Border Styles
    BORDER_PRIMARY = "cyan"
    BORDER_SUCCESS = "green"
    BORDER_WARNING = "yellow"
    BORDER_ERROR = "red"
    
    # Text Icons (Windows-compatible, no emojis)
    ICON_FILE = "[FILE]"
    ICON_DIFF = "[DIFF]"
    ICON_THINK = "[THINK]"
    ICON_SUMMARY = "[SUM]"
    ICON_LOCK = "[LOCK]"
    ICON_OK = "[OK]"
    ICON_ERROR = "[X]"
    ICON_PENDING = "[...]"
    ICON_SEARCH = "[FIND]"
    ICON_EDIT = "[EDIT]"
    
    # Status Icons
    STATUS_PENDING = "○"
    STATUS_IN_PROGRESS = "◐"
    STATUS_COMPLETED = "●"
    STATUS_FAILED = "✗"
    STATUS_SKIPPED = "⊘"
    
    # Panel Settings
    PANEL_PADDING = (0, 1)
    PANEL_TITLE_ALIGN = "left"
    
    # Syntax Highlighting
    SYNTAX_THEME = "monokai"
    SYNTAX_LINE_NUMBERS = True
```

**Migration Strategy:**
1. Create theme.py
2. Update all UI files to import from theme.py
3. Replace hardcoded colors/icons with theme constants
4. Remove duplicate console instances

**Estimated Effort:** 2-3 hours
**Impact:** High (eliminates inconsistency)

---

## Phase 2: Status Bar Component

### 2.1 Create Persistent Status Bar

**File:** `cortex/ui/status_bar.py` (NEW)

**Purpose:** Show persistent context information at the bottom of the screen.

**Features:**
- Current model name
- Token usage (current/max)
- Message count
- Active operation count
- UI mode indicator
- Connection status

**Implementation Approach:**
```python
class StatusBar:
    """Persistent status bar for Cortex"""
    
    def __init__(self, console: Console):
        self.console = console
        self._visible = False
        self._data = {}
    
    def update(self, **kwargs):
        """Update status bar data"""
        self._data.update(kwargs)
        if self._visible:
            self._render()
    
    def _render(self):
        """Render status bar at bottom"""
        # Format: [cortex] 3 ops | 12.4k/128k tokens | 21 msgs | mimo-v2-flash | [MINIMAL]
        pass
```

**Integration Points:**
- Hook into agent's conversation updates
- Update on tool execution start/complete
- Show/hide based on UI mode

**Estimated Effort:** 3-4 hours
**Impact:** High (professional feel, constant context awareness)

---

## Phase 3: Content Folding

### 3.1 Implement Smart Content Folding

**File:** Modify `cortex/ui/display.py`

**Purpose:** Auto-collapse long outputs with expand option.

**Features:**
- Show first N lines by default
- "... (X more lines)" indicator
- Click/keyboard to expand
- Configurable fold threshold per content type

**Implementation:**
```python
def show_foldable_content(
    content: str,
    title: str,
    max_lines: int = 10,
    fold_indicator: str = "... ({remaining} more lines)",
    syntax: Optional[str] = None
):
    """Display content with folding support"""
    lines = content.split("\n")
    
    if len(lines) <= max_lines:
        # Show all content
        display_full(content, title, syntax)
    else:
        # Show folded preview
        preview = "\n".join(lines[:max_lines])
        remaining = len(lines) - max_lines
        preview += f"\n[dim]{fold_indicator.format(remaining=remaining)}[/dim]"
        display_preview(preview, title, syntax, total_lines=len(lines))
```

**Content Types to Support:**
- File reads (fold after 20 lines)
- Search results (fold after 10 results)
- Tool output (fold after 5 lines)
- Error traces (fold after 10 lines)

**Estimated Effort:** 4-5 hours
**Impact:** Medium (cleaner output, less scrolling)

---

## Phase 4: Animation Polish

### 4.1 Add Subtle Animations

**File:** Modify `cortex/ui/consolidated_display.py`

**Purpose:** Smooth transitions for status changes.

**Features:**
- Brief highlight when operation completes
- Smooth progress bar updates
- Fade-in for new content
- Spinner variations per operation type

**Implementation:**
```python
def _animate_status_change(
    self,
    operation_id: str,
    old_status: OperationStatus,
    new_status: OperationStatus
):
    """Animate the status change with brief highlight"""
    # Flash the row briefly when status changes to completed/failed
    if new_status in [OperationStatus.COMPLETED, OperationStatus.FAILED]:
        self._flash_row(operation_id, new_status)

def _flash_row(self, operation_id: str, status: OperationStatus):
    """Brief highlight animation for row"""
    # Use Rich's Text with reverse video briefly, then normal
    pass
```

**Animation Guidelines:**
- Keep animations under 300ms
- Don't animate on every update (only significant changes)
- Respect minimal mode (no animations)
- Support `--no-animation` flag

**Estimated Effort:** 3-4 hours
**Impact:** Medium (polished feel)

---

## Phase 5: Enhanced Diff Display

### 5.1 Improve Diff Visualization

**File:** Modify `cortex/ui/display.py` - `show_file_diff()`

**Purpose:** More readable, syntax-aware diffs.

**Features:**
- Side-by-side view option
- Word-level diff highlighting
- Syntax-aware coloring
- Collapsible unchanged regions
- Line numbers for both versions

**Implementation:**
```python
def show_file_diff_enhanced(
    old_content: str,
    new_content: str,
    path: str,
    mode: str = "unified",  # unified, side-by-side
    context_lines: int = 3
):
    """Enhanced diff with syntax highlighting and word-level diffs"""
    
    if mode == "side-by-side" and not is_minimal_mode():
        return _show_side_by_side_diff(old_content, new_content, path)
    
    # Unified diff with improvements
    diff = difflib.unified_diff(
        old_content.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
        lineterm="",
        n=context_lines
    )
    
    # Process with syntax highlighting
    return _render_diff_with_syntax(diff, path)

def _show_side_by_side_diff(old_content, new_content, path):
    """Side-by-side diff view using Rich Columns"""
    from rich.columns import Columns
    from rich.padding import Padding
    
    # Create two panels side by side
    old_panel = Panel(
        Syntax(old_content, path.split(".")[-1], theme="monokai"),
        title=f"[red]OLD: {path}[/red]",
        border_style="red"
    )
    new_panel = Panel(
        Syntax(new_content, path.split(".")[-1], theme="monokai"),
        title=f"[green]NEW: {path}[/green]",
        border_style="green"
    )
    
    console.print(Columns([old_panel, new_panel]))
```

**Estimated Effort:** 4-6 hours
**Impact:** Medium-High (better code review experience)

---

## Phase 6: Accessibility Mode

### 6.1 Add High-Contrast & Screen Reader Support

**File:** `cortex/ui/accessibility.py` (NEW)

**Purpose:** Make Cortex usable for everyone.

**Features:**
- High-contrast color scheme
- No-color mode (text-only indicators)
- Screen reader announcements
- Large text mode
- Keyboard navigation helpers

**Implementation:**
```python
class AccessibilityMode:
    """Accessibility settings for Cortex"""
    
    def __init__(self):
        self.high_contrast = False
        self.no_color = False
        self.screen_reader = False
        self.large_text = False
    
    def enable_high_contrast(self):
        """Use high-contrast color scheme"""
        self.high_contrast = True
        # Override theme colors
        UITheme.PRIMARY = "white"
        UITheme.SUCCESS = "bright_green"
        UITheme.WARNING = "bright_yellow"
        UITheme.ERROR = "bright_red"
        UITheme.BORDER = "white"
    
    def enable_no_color(self):
        """Text-only mode for screen readers"""
        self.no_color = True
        # Use [OK], [ERR], [WARN] prefixes instead of colors
```

**CLI Integration:**
```bash
cortex --accessibility high-contrast
cortex --no-color
cortex --large-text
```

**Estimated Effort:** 6-8 hours
**Impact:** High (inclusivity, compliance)

---

## Summary Timeline

| Phase | Task | Duration | Priority |
|-------|------|----------|----------|
| 1 | Theme System | 2-3 hrs | 🔴 Critical |
| 2 | Status Bar | 3-4 hrs | 🔴 Critical |
| 3 | Content Folding | 4-5 hrs | 🟡 Medium |
| 4 | Animation Polish | 3-4 hrs | 🟡 Medium |
| 5 | Enhanced Diff | 4-6 hrs | 🟡 Medium |
| 6 | Accessibility | 6-8 hrs | 🟢 Lower |

**Total Estimated Effort:** 22-30 hours
**Recommended Team:** 1-2 developers
**Timeline:** 1-2 weeks (part-time)

---

## Success Metrics

1. **Visual Consistency**: All UI elements use theme constants (0 hardcoded colors)
2. **User Experience**: Status bar provides constant context awareness
3. **Accessibility**: Passes basic screen reader tests, high-contrast mode works
4. **Performance**: No noticeable lag in live display updates
5. **Backward Compatibility**: All existing commands work unchanged

---

This plan provides a roadmap to elevate Cortex's UI from functional to polished and professional, matching the quality of tools like Claude Code while maintaining the flexibility and power users expect.