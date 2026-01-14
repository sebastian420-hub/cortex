# AST Integration Design for Cortex

## Overview
This document outlines the design for integrating tree-sitter AST parsing into Cortex to enable smart code understanding, moving beyond text-based search to semantic code analysis.

## Goals
1. **Enhanced Code Understanding**: Provide structural awareness of codebases
2. **Precise Operations**: Enable accurate refactoring and code manipulation
3. **Smart Context Selection**: Select relevant code snippets based on structure
4. **Performance**: Maintain or improve search performance with AST caching
5. **Backward Compatibility**: Enhance existing tools without breaking them

## Architecture

### Components

#### 1. AST Service Layer
```
cortex/ast/
├── service.py          # Main AST service with caching
├── parser.py           # Tree-sitter parser wrapper
├── queries.py          # Predefined AST queries
├── cache.py            # AST caching with LRU
└── languages.py        # Language-specific configurations
```

#### 2. Enhanced Tools
```
cortex/tools/ast/
├── ast_search_tool.py      # AST-aware search (enhances grep)
├── ast_extract_tool.py     # Extract code structures
├── ast_analyze_tool.py     # Code analysis (dependencies, complexity)
└── ast_refactor_tool.py    # AST-based refactoring
```

#### 3. Integration Points
- **grep_tool.py**: Add AST-aware search mode
- **agent.py**: Integrate AST context selection
- **core/context.py**: Use AST for smart context window management

## Detailed Design

### AST Service Implementation

```python
class ASTService:
    """Central AST parsing and caching service"""
    
    def __init__(self, cache_size: int = 100):
        self.parsers = {}  # language -> parser
        self.cache = LRUCache(cache_size)
        self.file_hashes = {}  # file -> hash for change detection
        
    def parse_file(self, file_path: Path, language: str = None) -> AST:
        """Parse file into AST with caching"""
        # 1. Detect language if not specified
        # 2. Check cache with file hash validation
        # 3. Parse with tree-sitter
        # 4. Cache result
        pass
    
    def query(self, file_path: Path, query_pattern: str) -> List[Match]:
        """Execute tree-sitter query on file"""
        pass
    
    def extract_functions(self, file_path: Path) -> List[FunctionInfo]:
        """Extract all function definitions"""
        pass
    
    def find_usages(self, file_path: Path, symbol: str) -> List[Usage]:
        """Find all usages of a symbol"""
        pass
```

### AST-Aware Search Tool

```python
class ASTSearchTool(Tool):
    """Enhanced search with AST understanding"""
    
    def execute(self, pattern: str, search_type: str = "smart", **kwargs):
        """
        search_type options:
        - "text": Traditional grep (fallback)
        - "structure": AST pattern matching
        - "smart": Auto-detect based on pattern
        - "function": Search function definitions
        - "class": Search class definitions
        """
        if search_type == "smart":
            # Analyze pattern to determine best approach
            if self._looks_like_structural_pattern(pattern):
                return self._ast_search(pattern, **kwargs)
            else:
                return self._text_search(pattern, **kwargs)
        elif search_type == "structure":
            return self._ast_search(pattern, **kwargs)
        else:
            return self._text_search(pattern, **kwargs)
```

### Language Support Matrix

| Language | Parser | Priority | Features |
|----------|--------|----------|----------|
| Python | tree-sitter-python | High | Functions, classes, imports, decorators |
| JavaScript | tree-sitter-javascript | High | Functions, classes, imports, JSX |
| TypeScript | tree-sitter-typescript | High | Types, interfaces, generics |
| Java | tree-sitter-java | Medium | Classes, methods, annotations |
| Go | tree-sitter-go | Medium | Functions, structs, interfaces |
| Rust | tree-sitter-rust | Medium | Functions, structs, traits |
| C/C++ | tree-sitter-cpp | Low | Functions, classes, macros |

## Integration with Existing Tools

### 1. Enhanced Grep Tool
- Add `search_type` parameter to existing grep tool
- Auto-detect when to use AST vs text search
- Provide better results for code patterns

### 2. Smart Context Selection
```python
class ASTContextSelector:
    """Select relevant code context using AST"""
    
    def select_context(self, task: str, current_file: str) -> str:
        # 1. Parse current file AST
        # 2. Identify relevant symbols
        # 3. Find related code
        # 4. Extract semantic chunks
        pass
```

### 3. Refactoring Tools
- Rename symbols with 100% accuracy
- Extract functions/methods
- Move code between files
- Update imports and references

## Performance Considerations

### Caching Strategy
- **AST Cache**: LRU cache for parsed ASTs
- **File Hash Validation**: Detect file changes
- **Incremental Parsing**: Use tree-sitter's incremental capabilities
- **Selective Parsing**: Only parse when needed

### Memory Management
- Configurable cache size
- Clear cache on memory pressure
- Lazy loading of language parsers

## Error Handling and Fallbacks

### Graceful Degradation
1. **Parser Not Available**: Fall back to text search
2. **Parsing Error**: Log error, use text search
3. **Unsupported Language**: Use file extension detection
4. **Large Files**: Use streaming/chunked parsing

### User Feedback
- Show when AST parsing is being used
- Indicate language detection results
- Provide suggestions for better patterns

## Implementation Phases

### Phase 1: Foundation (2 weeks)
- Add tree-sitter dependency
- Implement basic AST service
- Create AST search tool for Python
- Integrate with existing grep tool

### Phase 2: Enhancement (3 weeks)
- Add support for JavaScript/TypeScript
- Implement semantic chunking
- Create context selection
- Add basic refactoring tools

### Phase 3: Advanced Features (3 weeks)
- Add more language support
- Implement dependency analysis
- Create code visualization
- Add test generation from AST

### Phase 4: Optimization (2 weeks)
- Performance tuning
- Memory optimization
- Caching improvements
- User experience polish

## Testing Strategy

### Unit Tests
- AST parsing correctness
- Query execution
- Cache behavior
- Error handling

### Integration Tests
- Tool integration
- End-to-end search scenarios
- Refactoring operations
- Performance benchmarks

### Compatibility Tests
- Cross-platform testing
- Large codebase handling
- Edge cases and error conditions

## Success Metrics

### Quantitative
- Search accuracy improvement (%)
- Refactoring success rate (%)
- Context relevance score
- Performance impact (ms)
- Memory usage (MB)

### Qualitative
- User satisfaction with search results
- Ease of refactoring operations
- Quality of context selection
- Overall developer experience

## Risks and Mitigations

### Technical Risks
1. **Performance Impact**: Profile and optimize, use caching
2. **Memory Usage**: Implement configurable limits, lazy loading
3. **Parser Quality**: Use well-maintained parsers, have fallbacks
4. **Language Support**: Start with core languages, expand gradually

### Integration Risks
1. **Breaking Changes**: Maintain backward compatibility
2. **User Adoption**: Provide clear benefits, gradual rollout
3. **Complexity**: Keep API simple, document thoroughly

## Future Extensions

### Short-term
- MCP server for AST analysis
- IDE integration
- Batch processing

### Long-term
- Machine learning on AST patterns
- Code smell detection
- Automated refactoring suggestions
- Team collaboration features

## Conclusion

AST integration will transform Cortex from a text-based coding assistant to a structurally-aware development partner. The phased approach ensures stable delivery while providing immediate value through enhanced search capabilities.