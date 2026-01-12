# Cortex v2.0 Design Specifications

## Overview

This directory contains comprehensive design specifications for evolving Cortex into a production-ready AI coding assistant with features comparable to Claude Code.

## Documents

| Document | Description |
|----------|-------------|
| [DESIGN_SPECIFICATIONS.md](./DESIGN_SPECIFICATIONS.md) | Main specification document with Phase 1 details |
| [PHASE2_SPECS.md](./PHASE2_SPECS.md) | Advanced features: Subagents, Skills, Background Tasks |
| [PHASE3_SPECS.md](./PHASE3_SPECS.md) | Code refactoring: System prompt, Split agent.py, TypedDict |
| [PHASE4_SPECS.md](./PHASE4_SPECS.md) | Extended features: Web, Multimodal, MCP Protocol |

## Quick Reference

### Implementation Phases

```
Phase 1: Core Robustness (Priority: P0-P1)
├── 1.1 Context Summarization System
├── 1.2 Ask User Questions Tool
├── 1.3 Todo Tracking Tool
└── 1.4 Secure Session File Permissions

Phase 2: Advanced Features (Priority: P1-P2)
├── 2.1 Typed Subagents System (Explore, Plan, Bash)
├── 2.2 Slash Commands / Skills System
├── 2.3 Background Task Execution
└── 2.4 Enhanced Plan Mode

Phase 3: Code Refactoring (Priority: P1-P2)
├── 3.1 Extract System Prompt Builder
├── 3.2 Split agent.py into Modules
└── 3.3 Add TypedDict Types

Phase 4: Extended Features (Priority: P3-P4)
├── 4.1 Web Search and Fetch
├── 4.2 Multimodal Support (Images, PDF, Notebooks)
└── 4.3 MCP Protocol Support
```

### Priority Guide

| Priority | Meaning | Effort |
|----------|---------|--------|
| P0 | Critical - Do first | < 4 hours |
| P1 | High - Core functionality | 4-12 hours |
| P2 | Medium - Important but not blocking | 12-24 hours |
| P3 | Low - Nice to have | 24+ hours |
| P4 | Future - Long term | Multiple weeks |

### Quick Wins (< 1 hour each)

1. **Session file permissions** - Add `os.umask(0o077)` in sessions.py
2. **Better cleanup logging** - Log errors instead of silencing them
3. **Add basic TypedDict for ToolResult** - Single type definition

### Recommended Implementation Order

1. **Session Permissions** (P0) - 30 minutes
2. **Todo Tracking Tool** (P0) - 4 hours
3. **Ask User Questions Tool** (P0) - 4 hours
4. **Extract System Prompt** (P1) - 2 hours
5. **Context Summarization** (P1) - 8 hours
6. **Split agent.py** (P1) - 4 hours
7. **TypedDict Types** (P2) - 4 hours
8. **Typed Subagents** (P1) - 12 hours
9. **Slash Commands** (P2) - 8 hours
10. **Background Tasks** (P2) - 8 hours

## New Directory Structure

After implementation, the codebase should look like:

```
cortex/
├── agent.py                    # ~200 lines (refactored)
├── cli.py
├── config.py
├── models.py
├── types.py                    # NEW: TypedDict definitions
│
├── core/
│   ├── __init__.py
│   ├── context.py
│   ├── conversation.py
│   ├── loop_guards.py
│   ├── providers.py
│   ├── recovery.py
│   ├── security.py
│   ├── streaming.py
│   ├── system_prompt.py        # NEW: SystemPromptBuilder
│   ├── tool_executor.py        # NEW: Extracted from agent.py
│   ├── message_processor.py    # NEW: Extracted from agent.py
│   ├── summarization.py        # NEW: Context summarization
│   ├── plan_mode.py            # NEW: Plan mode state
│   └── background.py           # NEW: Background task manager
│
├── tools/
│   ├── __init__.py
│   ├── base.py
│   ├── registry.py
│   ├── file_tools.py
│   ├── command_tools.py
│   ├── git_tools.py
│   ├── search_tools.py
│   ├── test_tools.py
│   ├── ask_user_tool.py        # NEW: Ask user questions
│   ├── todo_tool.py            # NEW: Todo tracking
│   ├── plan_tools.py           # NEW: Plan mode tools
│   ├── web_tools.py            # NEW: Web search/fetch
│   ├── multimodal_tools.py     # NEW: Image, PDF, notebook
│   │
│   ├── web/                    # NEW: Web processing
│   │   ├── __init__.py
│   │   ├── search.py
│   │   ├── fetch.py
│   │   └── sanitizer.py
│   │
│   └── multimodal/             # NEW: Multimodal processing
│       ├── __init__.py
│       ├── image.py
│       ├── pdf.py
│       └── notebook.py
│
├── subagent/
│   ├── __init__.py
│   ├── base.py                 # NEW: BaseSubagent class
│   ├── types.py                # NEW: SubagentType configs
│   ├── context.py
│   ├── task_tool.py
│   ├── manager.py              # NEW: Subagent orchestration
│   ├── explore_agent.py        # NEW: Explore agent
│   ├── plan_agent.py           # NEW: Plan agent
│   └── bash_agent.py           # NEW: Bash agent
│
├── skills/                     # NEW: Skill system
│   ├── __init__.py
│   ├── base.py
│   ├── registry.py
│   ├── commit.py
│   ├── review_pr.py
│   ├── init.py
│   └── help.py
│
├── mcp/                        # NEW: MCP protocol
│   ├── __init__.py
│   ├── client.py
│   ├── server.py
│   ├── transport.py
│   ├── protocol.py
│   └── tools.py
│
├── hooks/
│   └── ... (unchanged)
│
├── storage/
│   └── ... (minor permission fixes)
│
├── output/
│   └── ... (unchanged)
│
├── ui/
│   ├── ... (existing)
│   └── todo_display.py         # NEW: Todo display
│
└── utils/
    └── ... (unchanged)
```

## Dependencies to Add

```
# requirements.txt additions

# Phase 1
# (no new dependencies)

# Phase 2
# (no new dependencies)

# Phase 3
# (no new dependencies)

# Phase 4
duckduckgo-search>=3.0.0
html2text>=2020.1.16
Pillow>=9.0.0
pymupdf>=1.23.0
```

## Testing Requirements

Each phase should include:
- Unit tests for new modules
- Integration tests for workflows
- Update existing tests as needed

Target test coverage: **60%** (up from current 39.6%)

## Getting Started

1. Review the main [DESIGN_SPECIFICATIONS.md](./DESIGN_SPECIFICATIONS.md)
2. Start with Quick Wins (session permissions, logging)
3. Implement Phase 1 features
4. Run tests and verify functionality
5. Proceed to subsequent phases

## Questions?

If you have questions about any specification, refer to the detailed design document or ask for clarification before implementing.
