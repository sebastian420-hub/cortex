# Plan Documentation Feature Implementation Plan

## Objective
Add automatic documentation generation for every plan created and executed by Cortex's planning system. Each plan will have a corresponding documentation file that captures the plan's goal, steps, execution results, and learnings.

## Background
The Cortex planning system (`cortex/core/planning.py`) currently:
- Generates plans with steps and metadata
- Executes plans step-by-step
- Saves plans as JSON via `save_plan()`
- Provides summary via `get_plan_summary()`

However, there's no human-readable documentation automatically generated for plans, which would be valuable for:
- Reviewing what the agent planned to do
- Understanding execution outcomes
- Tracking progress over time
- Knowledge sharing and audit trails

## Requirements

### Functional Requirements
1. **Automatic Documentation Generation**
   - Generate documentation when a plan is created
   - Update documentation when plan execution completes
   - Include execution results and outcomes

2. **Document Content**
   - Plan metadata (ID, goal, description, timestamps)
   - Success criteria, constraints, assumptions
   - Step-by-step breakdown with status and outcomes
   - Execution statistics (duration, success/failure counts)
   - Reflections and learnings
   - Related files or artifacts created

3. **File Management**
   - Store documentation in `.cortex/plans/` directory by default
   - Use naming convention: `<plan_id>.md` (e.g., `plan_20250115_1430_1234.md`)
   - Allow custom output directory configuration
   - Support both markdown and JSON formats

4. **Integration Points**
   - Integrate with `PlanningEngine.generate_plan()`
   - Integrate with `PlanningEngine.execute_plan()`
   - Integrate with `EnhancedCortex.generate_and_execute_plan()`
   - Provide CLI command to generate documentation for existing plans

5. **Configuration**
   - Enable/disable documentation generation
   - Choose output format (markdown, JSON, both)
   - Customize output directory
   - Template customization options

### Non-Functional Requirements
1. **Performance**
   - Documentation generation < 100ms per plan
   - No impact on plan execution performance
   - Minimal memory overhead

2. **Reliability**
   - Documentation generation failures don't break plan execution
   - Graceful handling of file system errors
   - Atomic writes to prevent corrupted files

3. **Usability**
   - Clean, readable markdown output
   - Consistent formatting across plans
   - Easy to find and browse plan documentation

## Design

### Architecture Overview

```
PlanningEngine
├── generate_plan() → Plan
├── execute_plan() → Dict[str, Any]
├── save_plan() → bool
├── load_plan() → Optional[Plan]
├── get_plan_summary() → str
└── generate_plan_documentation() → bool  # NEW
    └── uses PlanDocumentationGenerator
```

### New Components

#### 1. `PlanDocumentationGenerator` Class
```python
class PlanDocumentationGenerator:
    """Generates human-readable documentation for plans."""
    
    def __init__(self, output_dir: Path = Path(".cortex/plans")):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_markdown(self, plan: Plan, execution_result: Optional[Dict[str, Any]] = None) -> str:
        """Generate markdown documentation for a plan."""
    
    def generate_json(self, plan: Plan, execution_result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate structured JSON documentation."""
    
    def save_documentation(self, plan: Plan, format: str = "markdown", 
                          execution_result: Optional[Dict[str, Any]] = None) -> Path:
        """Save documentation to file and return path."""
```

#### 2. `PlanningEngine` Enhancements
Add new methods and configuration:

```python
class PlanningEngine:
    def __init__(self, ..., generate_docs: bool = True, docs_output_dir: Optional[Path] = None):
        self.generate_docs = generate_docs
        self.docs_generator = PlanDocumentationGenerator(
            output_dir=docs_output_dir or Path(".cortex/plans")
        )
    
    def generate_plan_documentation(self, plan: Plan, 
                                   execution_result: Optional[Dict[str, Any]] = None,
                                   format: str = "markdown") -> Optional[Path]:
        """Generate and save plan documentation."""
        
    def generate_and_save_plan(self, goal: str, ...) -> Plan:
        """Generate plan and immediately save documentation."""
```

#### 3. EnhancedCortex Integration
Update `generate_and_execute_plan()` to automatically generate documentation:

```python
def generate_and_execute_plan(self, goal: str) -> Dict[str, Any]:
    plan = self.planning_engine.generate_plan(goal)
    
    # Generate initial documentation (plan preview)
    if self.config.generate_plan_docs:
        self.planning_engine.generate_plan_documentation(plan, format="markdown")
    
    execution_result = self.planning_engine.execute_plan(plan)
    
    # Update documentation with execution results
    if self.config.generate_plan_docs:
        self.planning_engine.generate_plan_documentation(
            plan, execution_result=execution_result, format="markdown"
        )
    
    return execution_result
```

### Documentation Template

```markdown
# Plan: {plan.id}

## Overview
- **Goal:** {plan.goal}
- **Description:** {plan.description}
- **Status:** {plan.status.value}
- **Created:** {plan.created_at}
- **Started:** {plan.started_at}
- **Completed:** {plan.completed_at}
- **Priority:** {plan.priority}/5
- **Estimated Duration:** {plan.estimated_duration_minutes} minutes
- **Actual Duration:** {plan.actual_duration_minutes} minutes

## Context
### Success Criteria
{bullet_list(plan.success_criteria)}

### Constraints
{bullet_list(plan.constraints)}

### Assumptions
{bullet_list(plan.assumptions)}

## Execution Summary
- **Total Steps:** {progress.total}
- **Completed:** {progress.completed}
- **In Progress:** {progress.in_progress}
- **Failed:** {progress.failed}
- **Completion:** {progress.completion_percentage:.1f}%

## Steps

| Step | Type | Description | Status | Outcome |
|------|------|-------------|--------|---------|
{step_rows}

## Execution Results
```json
{execution_result_json}
```

## Reflections
{reflections_section}

## Files & Artifacts
{list_of_created_files}

## Related Plans
{links_to_related_plans}
```

## Implementation Plan

### Phase 1: Core Documentation Generator (Week 1)

#### 1.1 Create `PlanDocumentationGenerator` Class
- Location: `cortex/core/plan_documentation.py`
- Implement markdown generation with template
- Implement JSON generation
- Add file saving with atomic writes
- Unit tests for all methods

#### 1.2 Enhance `PlanningEngine` Class
- Add `generate_docs` parameter to constructor
- Add `docs_output_dir` configuration
- Add `generate_plan_documentation()` method
- Integrate with existing `save_plan()` method
- Update tests to cover new functionality

### Phase 2: Integration & Configuration (Week 2)

#### 2.1 EnhancedCortex Integration
- Add configuration option in `AgentConfig`
- Update `EnhancedCortex.__init__()` to pass config to planning engine
- Modify `generate_and_execute_plan()` to generate documentation
- Add CLI flag `--plan-docs` to enable/disable

#### 2.2 Configuration System
- Add to `config/default.yaml`:
  ```yaml
  planning:
    generate_documentation: true
    documentation_format: "markdown"  # markdown, json, both
    documentation_directory: ".cortex/plans"
  ```
- Environment variable support: `CORTEX_PLAN_DOCS=true`
- Command-line flag: `--plan-docs-format markdown`

### Phase 3: Advanced Features (Week 3)

#### 3.1 Documentation Templates
- Support custom templates via file
- Template variables system
- Default template with good formatting

#### 3.2 CLI Commands
- `cortex plan docs <plan_id>` - Generate documentation for existing plan
- `cortex plan list` - List all plans with links to documentation
- `cortex plan show <plan_id>` - Show plan summary and documentation

#### 3.3 Cross-Plan References
- Track related plans
- Generate plan family trees
- Documentation navigation

### Phase 4: Testing & Polish (Week 4)

#### 4.1 Comprehensive Testing
- Unit tests for documentation generation
- Integration tests with planning engine
- End-to-end tests with EnhancedCortex
- Performance benchmarks

#### 4.2 User Experience
- Documentation preview in console
- Error handling and user feedback
- Documentation quality validation

#### 4.3 Documentation
- Update `README.md` with new feature
- Add examples of plan documentation
- Update help system with new commands

## Configuration Options

### Agent Configuration
```python
class AgentConfig:
    def __init__(self, ...,
                 # Plan documentation settings
                 plan_documentation: Optional[Dict[str, Any]] = None):
        
        self.plan_documentation = {
            "enabled": True,
            "format": "markdown",  # markdown, json, both
            "output_dir": ".cortex/plans",
            "template": None,  # Path to custom template
            ** (plan_documentation or {})
        }
```

### Environment Variables
- `CORTEX_PLAN_DOCS_ENABLED=true/false`
- `CORTEX_PLAN_DOCS_FORMAT=markdown`
- `CORTEX_PLAN_DOCS_DIR=/path/to/docs`

### CLI Flags
- `--plan-docs` / `--no-plan-docs`
- `--plan-docs-format markdown`
- `--plan-docs-dir ./docs/plans`

## Example Usage

### Basic Usage
```python
agent = EnhancedCortex(
    project_dir=".",
    enable_planning=True,
    config=AgentConfig(
        plan_documentation={"enabled": True, "format": "markdown"}
    )
)

result = agent.generate_and_execute_plan(
    "Add authentication to the API endpoints"
)
# Documentation automatically generated at .cortex/plans/plan_20250115_1430_5678.md
```

### CLI Usage
```bash
# Run with plan documentation
cortex --plan-docs --plan-docs-format markdown

# Generate docs for existing plan
cortex plan docs plan_20250115_1430_5678

# List all plans
cortex plan list
```

## Expected Output

### Generated Markdown File (.cortex/plans/plan_20250115_1430_5678.md)
```markdown
# Plan: plan_20250115_1430_5678

## Overview
- **Goal:** Add authentication to the API endpoints
- **Status:** completed
- **Created:** 2025-01-15T14:30:00.123456
- **Started:** 2025-01-15T14:30:05.234567
- **Completed:** 2025-01-15T14:35:22.345678
- **Actual Duration:** 5.28 minutes

## Context
### Success Criteria
- All API endpoints require authentication
- JWT tokens validated correctly
- Error responses for invalid tokens

### Constraints
- Must maintain backward compatibility
- Use existing user database

## Execution Summary
- **Total Steps:** 6
- **Completed:** 6
- **Failed:** 0
- **Completion:** 100.0%

## Steps
| Step | Type | Description | Status | Outcome |
|------|------|-------------|--------|---------|
| 1 | subtask | Analyze authentication requirements | ✅ | Requirements understood |
| 2 | tool_call | Read current API code | ✅ | Read 3 API endpoint files |
| 3 | tool_call | Add JWT middleware | ✅ | Middleware added to app.py |
| 4 | tool_call | Update endpoints | ✅ | Updated 3 endpoints |
| 5 | tool_call | Write tests | ✅ | Created test_auth.py |
| 6 | checkpoint | Verify implementation | ✅ | All tests passing |

## Files Created
- `middleware/auth.py` - JWT authentication middleware
- `tests/test_auth.py` - Authentication tests
- `.cortex/plans/plan_20250115_1430_5678.md` - This documentation

## Reflections
- Successfully implemented JWT authentication
- All tests pass
- Consider adding rate limiting in future iteration
```

## Technical Details

### File Structure
```
.cortex/
├── plans/
│   ├── plan_20250115_1430_1234.md
│   ├── plan_20250115_1500_5678.md
│   └── plan_20250115_1600_9012.json
├── sessions/
└── backups/
```

### Atomic Writes
To prevent corrupted documentation files:
```python
def safe_write(path: Path, content: str) -> bool:
    temp_path = path.with_suffix(".tmp")
    try:
        temp_path.write_text(content, encoding="utf-8")
        temp_path.replace(path)  # Atomic rename
        return True
    except Exception as e:
        logger.error(f"Failed to write {path}: {e}")
        return False
```

### Template System
```python
class PlanTemplate:
    def render(self, plan: Plan, context: Dict[str, Any]) -> str:
        # Use Jinja2 or simple string formatting
        template = self._load_template()
        return template.format(**self._prepare_context(plan, context))
```

## Testing Strategy

### Unit Tests
- `test_plan_documentation_generator.py`
  - Test markdown generation
  - Test JSON generation
  - Test file saving
  - Test template rendering

### Integration Tests
- `test_planning_with_docs.py`
  - Generate plan with documentation enabled
  - Verify documentation file created
  - Verify content matches plan
  - Test with execution results

### End-to-End Tests
- `test_enhanced_cortex_docs.py`
  - Full agent workflow with documentation
  - CLI command testing
  - Configuration options

## Risks & Mitigations

### Risk 1: Performance Impact
- **Mitigation**: Generate documentation asynchronously
- **Mitigation**: Make documentation generation optional
- **Mitigation**: Use efficient template rendering

### Risk 2: File System Errors
- **Mitigation**: Atomic writes prevent corruption
- **Mitigation**: Fallback to memory-only mode
- **Mitigation**: Comprehensive error logging

### Risk 3: Documentation Quality
- **Mitigation**: Provide customizable templates
- **Mitigation**: Include validation for required fields
- **Mitigation**: User feedback mechanism

## Success Metrics

1. **Adoption**: >80% of users enable plan documentation
2. **Performance**: <100ms documentation generation time
3. **Reliability**: 99.9% successful documentation generation
4. **Usability**: Users can find and read plan documentation easily

## Future Enhancements

### 1. Interactive Documentation
- Web interface for browsing plans
- Search across plan documentation
- Visualizations of plan execution

### 2. AI-Powered Summaries
- LLM-generated executive summaries
- Automatic tagging and categorization
- Insight extraction from plan outcomes

### 3. Integration with Other Systems
- Export to Confluence, Notion, etc.
- GitHub PR comments with plan summary
- Slack notifications for plan completion

### 4. Advanced Analytics
- Plan success rate tracking
- Common failure patterns
- Optimization suggestions based on historical plans

## Timeline & Resources

### Timeline (4 weeks)
- **Week 1**: Core documentation generator
- **Week 2**: Integration & configuration
- **Week 3**: Advanced features & CLI
- **Week 4**: Testing, polish, documentation

### Resource Requirements
- **Primary Developer**: 1 FTE (4 weeks)
- **QA Engineer**: 0.5 FTE (2 weeks)
- **Technical Writer**: 0.25 FTE (1 week) for documentation

## Conclusion

Automatic plan documentation will significantly enhance Cortex's value by:
1. **Improving transparency**: Users can see what the agent planned and executed
2. **Enabling audit trails**: Track AI agent decisions and outcomes
3. **Facilitating collaboration**: Share plan documentation with team members
4. **Supporting learning**: Analyze past plans to improve future performance

The implementation follows Cortex's existing architecture patterns and maintains backward compatibility while adding significant new functionality.