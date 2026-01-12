# Debugging Skill

## Overview
This skill guides the agent through systematic debugging of issues in code. Focuses on hypothesis-driven investigation, root cause analysis, and creating targeted fixes.

## When to Use
- Tests are failing
- Runtime errors or exceptions occur
- Unexpected behavior or incorrect output
- Performance issues
- Intermittent/flaky failures

## Skill Steps

### 1. Reproduce the Issue
- Get clear steps to reproduce
- Identify consistent vs intermittent failures
- Determine if issue is environment-specific
- Create minimal reproduction if possible

### 2. Gather Information
- Error messages and stack traces
- Logs and output
- Input data that triggers the issue
- Environment details (OS, Python version, dependencies)

### 3. Form Hypotheses
- Based on symptoms, propose possible causes
- Start with most likely/common causes
- Consider recent changes that might have introduced issue
- Look for similar past issues

### 4. Investigate Systematically
- Use debugging tools (print statements, debugger, logging)
- Add instrumentation to gather more data
- Isolate components to narrow down cause
- Create tests that reproduce the issue

### 5. Identify Root Cause
- Don't just fix symptoms
- Understand why the issue occurs
- Consider underlying design problems
- Check for related issues that might appear later

### 6. Develop Fix
- Create minimal fix that addresses root cause
- Consider trade-offs (quick fix vs proper solution)
- Ensure fix doesn't break other functionality
- Add tests to prevent regression

### 7. Verify Fix
- Issue is resolved
- No new issues introduced
- Tests pass
- Edge cases handled

### 8. Document Learnings
- Update documentation if API/behavior changed
- Add comments explaining the fix
- Consider if similar issues exist elsewhere
- Share insights with team

## Tool Usage Patterns

### Investigation
```python
# Search for error messages
grep(pattern="Error message text", file_type="py", output_mode="files_with_matches")

# Look for recent changes
git_log(limit=20)

# Check for similar issues in code
grep(pattern="TODO|FIXME|BUG|XXX", file_type="py", output_mode="content")
```

### Testing Hypotheses
```python
# Add debug output via edit
edit(
    file_path="module.py",
    old_string="result = calculate(data)",
    new_string="import logging\nlogger = logging.getLogger(__name__)\nlogger.debug(f'Calculating with data: {data}')\nresult = calculate(data)\nlogger.debug(f'Result: {result}')"
)

# Create test to reproduce issue
write_file(path="tests/test_reproduce_issue.py", content=reproduction_test)
```

### Fix Application
```python
# Apply fix
edit(
    file_path="buggy_module.py",
    old_string="buggy_code",
    new_string="fixed_code"
)

# Add regression test
edit(
    file_path="tests/test_module.py",
    old_string="def test_normal_case():",
    new_string="def test_issue_fixed():\n    # Regression test for issue #123\n    assert fixed_function(bad_input) == expected_output\n\ndef test_normal_case():"
)
```

## Debugging Techniques

### For Runtime Errors
1. Examine stack trace
2. Check variable values at point of failure
3. Look for None values or type mismatches
4. Check boundary conditions

### For Logic Errors
1. Add assertions to check invariants
2. Use property-based testing
3. Compare actual vs expected step by step
4. Check algorithm assumptions

### For Performance Issues
1. Profile to find bottlenecks
2. Check for inefficient algorithms (O(n^2) where O(n) possible)
3. Look for unnecessary computations
4. Check memory usage

### For Intermittent Issues
1. Add more logging
2. Look for race conditions
3. Check for resource leaks
4. Consider external factors (network, filesystem)

## Common Root Causes

### Data Issues
- Incorrect assumptions about input format
- Missing or null values
- Off-by-one errors in loops
- Incorrect data transformations

### State Issues
- Shared mutable state
- Improper initialization
- Race conditions
- Memory leaks

### Logic Issues
- Incorrect condition checks
- Missing edge cases
- Algorithmic errors
- Misunderstood requirements

## Success Criteria
- Issue is consistently reproducible
- Root cause is understood
- Fix addresses root cause, not just symptoms
- No regressions introduced
- Tests exist to prevent recurrence

## Avoiding Common Pitfalls
- **Don't** make random changes hoping something works
- **Don't** fix symptoms without understanding cause
- **Don't** introduce bigger problems while fixing small ones
- **Do** work systematically
- **Do** keep notes of investigation
- **Do** verify fix thoroughly

## Integration with Other Skills
- Use with `TDD_WORKFLOW.md` for test-driven debugging
- Use with `REFACTOR_MODULE.md` when bugs reveal design issues
- Use with `API_MIGRATION.md` when debugging compatibility issues

## Example Workflow

**User Request**: "The report generation is failing with KeyError on 'total' field"

**Agent Action Plan**:
1. Get exact error: `grep(pattern="KeyError.*total", file_type="py", output_mode="content")`
2. Find report generation code: `grep(pattern="def generate_report", file_type="py")`
3. Trace data flow to find where 'total' field should be set
4. Add debug logging to see data state
5. Identify missing data calculation
6. Fix calculation or add default value
7. Add test for missing field case
8. Verify all reports generate correctly