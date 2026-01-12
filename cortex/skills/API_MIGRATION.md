# API Migration Skill

## Overview
This skill guides the agent through migrating an API or library interface while maintaining backward compatibility or providing clear migration paths. Useful for version upgrades, dependency changes, or interface improvements.

## When to Use
- Upgrading library versions with breaking changes
- Changing public API signatures
- Replacing deprecated functionality
- Moving between similar libraries (e.g., requests to httpx)
- Changing data formats or schemas

## Skill Steps

### 1. Understand Current API
- Identify all usages of the API/library
- Map out the current interface (functions, classes, methods)
- Understand the data flows and dependencies
- Check for any existing type hints or documentation

### 2. Understand Target API
- Review documentation of new API/library
- Identify mapping between old and new APIs
- Note breaking changes and compatibility issues
- Understand new features and improvements

### 3. Create Migration Strategy
**Options:**
- **Big Bang**: Change everything at once (risky, needs thorough testing)
- **Parallel Run**: Support both old and new APIs temporarily
- **Gradual Migration**: Migrate piece by piece with compatibility layer
- **Versioned API**: Keep old API version alongside new one

### 4. Implement Compatibility Layer (if needed)
- Create adapters/wrappers to translate between APIs
- Use feature flags or configuration to toggle between implementations
- Log usage of deprecated API to help track migration progress

### 5. Update Code Incrementally
- Start with low-risk, isolated components
- Update tests to work with new API
- Verify functionality after each change
- Use type checking and static analysis

### 6. Update Documentation
- Update API documentation, README, examples
- Add migration guide for users
- Update type hints and docstrings

### 7. Clean Up (after migration)
- Remove deprecated code and compatibility layers
- Update dependency versions
- Run final validation tests

## Tool Usage Patterns

### Code Analysis
```python
# Find all usages of a library/function
grep(pattern="import requests|from requests", file_type="py", output_mode="files_with_matches")
grep(pattern="requests\\.get|requests\\.post", file_type="py", output_mode="content")

# Find function signatures
grep(pattern="def api_function", file_type="py", output_mode="content")
```

### Safe Refactoring
```python
# Use edit for precise changes
edit(
    file_path="module.py",
    old_string="import requests",
    new_string="import httpx as requests  # TODO: Migrate to httpx"
)

# Create new version alongside old
write_file(path="new_api.py", content=new_implementation)
```

### Testing
```python
# Run tests to ensure no regressions
run_tests(pattern="test_api*.py")

# Create migration tests
write_file(path="tests/test_migration.py", content=migration_tests)
```

## Common Migration Patterns

### Library Upgrade (e.g., requests to httpx)
1. Add httpx as dependency
2. Create adapter that mimics requests API using httpx
3. Update imports to use adapter
4. Gradually update code to use native httpx features
5. Remove adapter when migration complete

### API Version Change (e.g., v1 to v2)
1. Keep v1 endpoints working
2. Add v2 endpoints alongside v1
3. Update clients to use v2
4. Monitor v1 usage
5. Deprecate and eventually remove v1

### Schema Migration (e.g., adding new required field)
1. Make field optional initially
2. Update all code to provide the field
3. Make field required
4. Remove fallback logic

## Success Criteria
- All tests pass with new API
- No breaking changes for users (or clear migration path)
- Performance not degraded
- New features are accessible
- Documentation is updated

## Risk Mitigation

### Before Migration
- Comprehensive test suite
- Back up current code
- Understand rollback procedure
- Communicate changes to team/users

### During Migration
- Small, incremental changes
- Frequent commits with clear messages
- Continuous integration checks
- Monitoring for errors

### After Migration
- Performance testing
- User acceptance testing
- Monitor error rates
- Gather feedback

## Integration with Other Skills
- Use with `TDD_WORKFLOW.md` for test-driven migration
- Use with `REFACTOR_MODULE.md` for large-scale refactoring
- Use with `DEBUG_ISSUE.md` when migration causes issues

## Example Workflow

**User Request**: "Migrate from psycopg2 to asyncpg"

**Agent Action Plan**:
1. Find psycopg2 usage: `grep(pattern="psycopg2|import psycopg", file_type="py")`
2. Analyze current database patterns (sync vs async needs)
3. Create asyncpg adapter with similar interface
4. Update one module at a time
5. Add async/await support gradually
6. Update tests to use async testing
7. Performance test both implementations
8. Remove psycopg2 dependency when migration complete