# Task: Continue Chunked Editing Implementation

## Overview
Continue implementing chunked editing support for Cortex, building on the analysis comparing Cortex's memory management with Taskmaster's chunked editing approach.

## Context

### Recent Analysis
Based on analysis of Cortex's current state vs Taskmaster's chunked editing capabilities:
- **Cortex has**: Basic memory management, token estimation, cost tracking, rate limiting, summarization
- **Cortex needs**: Surgical chunk editing, context window visualization, smart context injection, chunk-based file operations

### Key File Created
- `docs/COMPREHENSIVE_IMPROVEMENT_PLAN_V2.md` - Updated with current progress tracking

### Progress on Memory Management (M1.2)
- [ ] **M1.2 - Chunked edit support** (PENDING)
  - Edit files in place without full load
  - Use memory-mapped files for large edits
  - File: `cortex/tools/file_tools.py`

## Next Steps to Implement

### 1. Create Core Chunk Infrastructure (High Priority)
**Files to create:**
- `cortex/core/memory/chunk.py` - Define `EditChunk` and `ChunkType` classes
- `cortex/core/memory/chunking.py` - Chunking utilities and algorithms
- `cortex/core/memory/context_window.py` - Context window management
- `cortex/core/memory/token_budget.py` - Token budget enforcement

**Key classes:**
```python
@dataclass
class EditChunk:
    chunk_id: str
    chunk_type: ChunkType  # FILE_CONTENT, CONVERSATION_SUMMARY, etc.
    content: str
    original_length: int
    current_length: int
    token_estimate: int
    parent_context: Optional[str] = None
    metadata: dict = None
```

### 2. Implement ChunkedEditTool (High Priority)
**File to create:**
- `cortex/tools/chunked_edit_tool.py` - Surgical editing with chunks

**Key features:**
- Automatic chunking of large files
- Surgical editing of specific chunks
- Context-aware chunk selection
- Token budget enforcement
- Integration with existing file operations

### 3. Enhance File Tools (Medium Priority)
**File to modify:**
- `cortex/tools/file_tools.py`

**Enhancements:**
- Add chunking support to ReadFileTool
- Add streaming file reads (already has offset/limit)
- Better binary file handling (already implemented)
- File size warnings (already implemented)

### 4. Integrate with Agent (Medium Priority)
**File to modify:**
- `cortex/agent.py`

**Integration points:**
- Hook into `_call_model` for context injection
- Add context window visualization to console output
- Token budget tracking per operation

### 5. Testing (Medium Priority)
**Files to create:**
- `tests/unit/core/test_chunking.py` - Test chunk creation and manipulation
- `tests/unit/core/test_context_window.py` - Test context management
- `tests/unit/tools/test_chunked_edit.py` - Test chunked editing

## Acceptance Criteria

- [ ] Chunk infrastructure created with proper data structures
- [ ] ChunkedEditTool implemented and integrated
- [ ] Context window visualization working
- [ ] Token budget enforcement functional
- [ ] Existing file operations enhanced with chunking
- [ ] Tests written for new functionality
- [ ] Documentation updated (README, API docs)

## Estimated Effort
- **Phase 1 (Core chunking)**: 6-8 hours
- **Phase 2 (Integration)**: 2-3 hours
- **Phase 3 (Testing)**: 2-3 hours
- **Total**: 10-14 hours

## References
- Taskmaster implementation: Research shows Taskmaster uses `EditChunk` with chunk registry
- Cortex analysis: Current memory management has basic tools but lacks surgical editing
- Recent analysis: Detailed comparison in context window messages

## Priority
**HIGH** - This is a core memory management improvement that will enable:
- Better handling of large files
- Reduced memory usage
- More efficient context window utilization
- Better user experience with file operations
