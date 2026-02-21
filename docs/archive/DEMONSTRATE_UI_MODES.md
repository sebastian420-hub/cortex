# Cortex UI Modes - Live Demonstration

## How to Use the New UI Mode Feature

### Starting Cortex with Different Modes
```bash
# Start in Minimal Mode (like Claude Code - DEFAULT)
cortex --ui-mode minimal

# Start in Normal Mode (current Cortex with panels)
cortex --ui-mode normal

# Start in Debug Mode (development details)
cortex --ui-mode debug
```

### During Session
```
> Ctrl+T    # Toggle UI mode (cycles: minimal → normal → debug → minimal)
> /ui       # Show current UI mode
> /ui minimal  # Switch to minimal mode
> /ui normal   # Switch to normal mode  
> /ui debug    # Switch to debug mode
```

## Visual Comparison

### Minimal Mode (Claude Code Style)
```
[FILE] api.py (42 lines)
    1: from fastapi import FastAPI
    2: from typing import Optional
  ... (40 more lines)

[THINK] Analyzing the code structure...

[DIFF] api.py
  --- old/api.py+++ new/api.py@@ -1,3 +1,3 @@

[OK] Fixed null pointer - Updated line 42 (0.15s)
```

### Normal Mode (Current Cortex)
```
+------------------------------- [FILE] api.py -------------------------------+
|   1 from fastapi import FastAPI                                             |
|   2 from typing import Optional                                             |
|   3 ... (40 more lines)                                                     |
+-----------------------------------------------------------------------------+

+------------------------------ [THINK] Thinking -----------------------------+
| I'll analyze this file to find the bug...                                   |
+-----------------------------------------------------------------------------+

[OK] Operation complete - Fixed the issue (0.25s)
```

### Debug Mode
Same as Normal mode but with additional timing and details.

## What's Different in Minimal Mode

1. **No panels/borders** - Clean text output
2. **Text icons** instead of emojis (Windows compatible)
   - `[FILE]` instead of 📄
   - `[DIFF]` instead of 📊  
   - `[THINK]` instead of 💭
   - `[SUM]` instead of 📋
   - `[LOCK]` instead of 🔒
   - `[OK]` instead of ✓
   - `[X]` instead of ✗
3. **Collapsed thinking** - One line preview unless expanded
4. **Limited file preview** - Shows only 3 lines by default
5. **Simple diffs** - Shows first 10 diff lines

## Windows Compatibility
All emojis have been replaced with text equivalents for Windows terminal compatibility.

## Configuration
Default mode is `minimal` (Claude Code style). Change in:
- CLI: `--ui-mode minimal|normal|debug`
- Config file: Coming soon
- In-session: `/ui` command or `Ctrl+T`

## Try It Now!
```bash
# Start Cortex with minimal mode
cortex --ui-mode minimal

# Do some operations
> read api.py
> search for "def main"
> Ctrl+T  # Switch to normal mode
> read api.py  # See with panels
> Ctrl+T  # Switch to debug mode
> Ctrl+T  # Back to minimal mode
```

The feature is fully implemented and ready for use! Enjoy the cleaner Claude Code-style interface.