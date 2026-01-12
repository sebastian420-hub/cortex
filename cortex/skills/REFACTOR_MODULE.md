# Module Refactoring Skill

## Overview
This skill guides the agent through refactoring a code module to improve its design, readability, and maintainability without changing its external behavior. Focuses on structural improvements rather than bug fixes or feature additions.

## When to Use
- Code is hard to understand or maintain
- Module has grown too large (god object)
- Poor separation of concerns
- Duplicate code exists
- Need to prepare for new features
- Technical debt needs addressing

## Skill Steps

### 1. Understand Current Module
- Read the module thoroughly
- Identify responsibilities and concerns
- Map dependencies (imports and exports)
- Understand the public API
- Look for code smells:
  - Long methods/functions
  - Large classes
  - High cyclomatic complexity
  - Duplicate code
  - Tight coupling

### 2. Establish Safety Net
- Ensure tests exist and pass
- If no tests, write characterization tests
- Document current behavior (what, not how)
- Consider using property-based testing

### 3. Design Target Structure
- Define clear responsibilities for new modules/classes
- Plan separation of concerns
- Design interfaces between components
- Consider design patterns that fit the domain
- Keep changes incremental and reversible

### 4. Execute Refactoring Steps
**Recommended order:**
1. **Preserve Behavior**: All tests should continue to pass
2. **Make Changes in Small Steps**: Commit after each safe change
3. **Verify Continuously**: Run tests frequently
4. **Refactor, Then Optimize**: Don't mix refactoring with optimization

### 5. Common Refactoring Techniques
- **Extract Function/Method**: Turn code fragment into function
- **Extract Class**: Create new class from parts of existing class
- **Move Method/Field**: Move to more appropriate class
- **Replace Conditional with Polymorphism**
- **Introduce Parameter Object**
- **Split Phase**: Separate processing from output

### 6. Update Dependencies
- Update imports in other modules
- Ensure API compatibility or provide adapters
- Update documentation

### 7. Validate Results
- All tests pass
- Code is more readable and maintainable
- Responsibilities are clearer
- No regression in performance (unless intended)

## Tool Usage Patterns

### Code Analysis
```python
# Find large functions
grep(pattern="def .*", file_type="py", output_mode="content")

# Look for code smells
grep(pattern="if.*and.*or|try.*except.*except", file_type="py", output_mode="content")

# Find dependencies
grep(pattern="import |from ", file_type="py", output_mode="content")
```

### Safe Refactoring
```python
# Extract function using edit
edit(
    file_path="module.py",
    old_string="""def large_function():
    # ... many lines ...
    result = complex_calculation(data)
    # ... more lines ...""",
    new_string="""def large_function():
    # ... many lines ...
    result = _calculate_result(data)
    # ... more lines ...

def _calculate_result(data):
    return complex_calculation(data)"""
)

# Create new module
write_file(path="new_module.py", content=extracted_code)
```

### Testing
```python
# Run tests after each change
run_tests(pattern="test_module*.py")

# Create integration tests
write_file(path="tests/test_refactored_integration.py", content=integration_tests)
```

## Refactoring Patterns

### Breaking God Class
1. Identify cohesive groups of methods
2. Extract each group to new class
3. Update references gradually
4. Consider using composition over inheritance

### Reducing Function Length
1. Identify logical sections
2. Extract each section to helper function
3. Give helper functions meaningful names
4. Consider if function should be a class

### Improving Error Handling
1. Centralize error handling logic
2. Create specific exception types
3. Add context to error messages
4. Ensure cleanup happens reliably

## Success Criteria
- External behavior unchanged
- Code is easier to read and understand
- Module is easier to test
- Responsibilities are clearly separated
- No new bugs introduced

## Risk Management
- **Version Control**: Use git frequently with descriptive commits
- **Rollback Plan**: Know how to revert if things go wrong
- **Peer Review**: Get feedback on major structural changes
- **Incremental Changes**: Don't try to fix everything at once

## Integration with Other Skills
- Use with `TDD_WORKFLOW.md` for test-first refactoring
- Use with `API_MIGRATION.md` when refactoring public APIs
- Use with `DEBUG_ISSUE.md` when refactoring reveals bugs

## Example Workflow

**User Request**: "Refactor the DataProcessor class - it's too large"

**Agent Action Plan**:
1. Read DataProcessor: `read_file(path="data_processor.py")`
2. Analyze methods: `grep(pattern="    def ", file_type="py", path="data_processor.py")`
3. Group related methods (parsing, validation, transformation, output)
4. Extract ValidationLogic class
5. Extract TransformationEngine class  
6. Update DataProcessor to use composed classes
7. Run tests after each extraction
8. Update documentation