# Test-Driven Development (TDD) Workflow Skill

## Overview
This skill guides the agent through a Test-Driven Development workflow for implementing new features or fixing bugs. TDD follows the "Red-Green-Refactor" cycle.

## When to Use
- Implementing new features with clear requirements
- Fixing bugs with reproducible test cases
- Refactoring existing code while ensuring behavior doesn't change
- Adding tests to untested code

## Skill Steps

### 1. Analyze Requirements
- Understand what needs to be implemented/fixed
- Identify test cases: happy path, edge cases, error conditions
- Determine existing test structure (pytest, unittest, etc.)

### 2. Write Failing Test (Red)
- Create or modify test file
- Write test that defines expected behavior
- Test should fail initially (RED state)
- Ensure test is specific and isolated

```python
# Example: Adding a new function
def test_new_feature():
    result = new_feature(input_data)
    assert result == expected_output
```

### 3. Implement Minimum Code (Green)
- Write the simplest code to make test pass
- Don't over-engineer - just make it work
- Verify test passes (GREEN state)

### 4. Refactor
- Improve code structure while keeping tests green
- Apply clean code principles:
  - Meaningful names
  - Single responsibility
  - DRY (Don't Repeat Yourself)
  - Proper error handling
- Run tests after each refactoring step

### 5. Repeat Cycle
- For each new requirement, repeat Red-Green-Refactor
- Build up functionality incrementally

## Tool Usage Patterns

### Test Discovery
```python
# Use grep to find existing tests
grep(pattern="def test_.*", file_type="py", output_mode="files_with_matches")
```

### Test Execution
```python
# Run specific test file
run_tests(pattern="test_feature.py")

# Run with verbose output
run_tests(pattern="test_feature.py", verbose=True)

# Run all tests
run_tests()
```

### File Operations
```python
# Read existing code
read_file(path="module.py")

# Write test file
write_file(path="tests/test_module.py", content=test_code)

# Edit implementation
edit(file_path="module.py", old_string="old_code", new_string="new_code")
```

## Common Patterns

### Adding New Function
1. Write test for function that doesn't exist yet
2. Create function with minimal implementation
3. Refactor for clarity and efficiency

### Fixing Bug
1. Write test that reproduces the bug (should fail)
2. Fix the bug in implementation
3. Verify test passes
4. Add additional tests for edge cases

### Refactoring Legacy Code
1. Write characterization tests for existing behavior
2. Refactor with confidence tests will catch regressions
3. Add missing tests incrementally

## Success Criteria
- All tests pass
- Code is clean and maintainable
- Edge cases are covered
- Test suite runs quickly
- Code coverage increases or stays high

## Anti-Patterns to Avoid
- Writing tests after implementation
- Tests that are too coupled to implementation
- Skipping the refactor step
- Tests that depend on external services
- Slow-running tests

## Integration with Other Skills
- Use with `API_MIGRATION.md` for API changes
- Use with `REFACTOR_MODULE.md` for larger refactorings
- Use with `DEBUG_ISSUE.md` when tests reveal bugs

## Example Workflow

**User Request**: "Add validation to the User class email field"

**Agent Action Plan**:
1. Find existing User tests: `grep(pattern="class.*TestUser|def test.*user", file_type="py")`
2. Read User class implementation: `read_file(path="models/user.py")`
3. Write failing test for email validation
4. Implement email validation in User class
5. Run tests to confirm they pass
6. Refactor validation logic if needed
7. Add edge case tests (empty email, invalid format, etc.)