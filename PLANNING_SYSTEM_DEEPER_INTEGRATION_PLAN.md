# Planning System Deeper Integration Plan

## Current Progress (Updated 2025)

**Phase 1 (Planning Tools) - COMPLETED** ✅
- Planning tools module implemented (`cortex/tools/planning_tools.py`)
- Tools registered in dynamic tool registry
- Parent agent integration working
- Tool schemas defined and exported
- All planning tools can be instantiated via `create_tool_instance`

**Remaining Work**: Continue with Phase 2 (Automatic Plan Detection) and beyond.

## Overview

The planning system in Cortex is currently functional but not deeply integrated into the agent's workflow. This plan outlines steps to make planning a first-class feature that's automatically used for complex tasks and exposed through dedicated tools.

## Current State Assessment

### ✅ **Working Components:**
- `PlanningEngine` class with full plan execution capabilities
- `Plan` and `PlanStep` data models with dependency tracking
- State management integration for tracking active plans
- Enhanced agent (`EnhancedCortex`) with planning engine initialization
- CLI support for enhanced mode (`--enhanced` flag)
- **Planning tools exposed to LLM**: `create_plan`, `execute_plan`, `monitor_plan`, `update_plan`
- Dynamic tool registry integration for planning tools

### ❌ **Integration Gaps:**
1. **✅ Planning tools now exposed to LLM** - Can create/execute plans via natural language (Phase 1 completed)
2. **Manual planning still required** - Must call planning tools explicitly; no automatic detection yet
3. **No automatic plan generation** - Doesn't detect complex tasks needing planning
4. **Limited plan adaptation** - No feedback loops for plan improvement
5. **No plan visualization** - Can't monitor or debug plan execution

## Integration Goals

### Primary Goals:
1. **Expose planning through tools**: Add `create_plan`, `execute_plan`, `monitor_plan` tools
2. **Automatic plan detection**: Automatically generate plans for complex multi-step tasks
3. **Plan-execution integration**: Seamlessly switch between planning and execution modes
4. **Plan adaptation**: Update plans based on execution results and obstacles
5. **Plan documentation**: Generate and save plan documentation for reference

### Secondary Goals:
1. **Plan templates**: Common patterns for tasks (refactoring, debugging, feature addition)
2. **Skill integration**: Better connection between planning and skill application
3. **Collaborative planning**: Human-AI collaborative plan refinement
4. **Plan persistence**: Save and reload plans across sessions

## Implementation Plan

### Phase 1: Planning Tools (Week 1) - COMPLETED ✅
**Objective**: Expose planning capabilities through LLM-accessible tools

1. **Create planning tools module** (`cortex/tools/planning_tools.py`) - COMPLETED:
   - `CreatePlanTool`: Generate plans from goal descriptions ✅
   - `ExecutePlanTool`: Execute existing plans ✅
   - `MonitorPlanTool`: Monitor plan progress and status ✅
   - `UpdatePlanTool`: Modify plans based on feedback ✅
   
2. **Register planning tools** in tool registry - COMPLETED:
   - Added to dynamic tool registry (not TOOLS list for backward compatibility) ✅
   - Proper permissions and safety checks implemented ✅
   - Parent agent integration working ✅
   
3. **Tool schemas design** - COMPLETED:
   - `create_plan`: goal, constraints, assumptions, skill_hints ✅
   - `execute_plan`: plan_id, max_steps, stop_on_failure ✅
   - `monitor_plan`: plan_id, detail_level ✅
   - `update_plan`: plan_id, modifications ✅
   
4. **Integration with enhanced agent** - COMPLETED:
   - Planning tools can be instantiated with parent_agent reference ✅
   - Tools check for planning engine availability ✅
   - Error handling for missing planning capabilities ✅

4. **Integration with enhanced agent**:
   - Planning tools should use existing `PlanningEngine`
   - Connect to state manager for plan tracking

### Phase 2: Automatic Plan Detection (Week 2)
**Objective**: Automatically generate plans for complex tasks

1. **Complexity heuristics**:
   - Analyze task description for multi-step indicators
   - Check for keywords: "implement", "refactor", "debug", "add feature"
   - Estimate task complexity based on project context
   
2. **Automatic plan trigger**:
   - Add to `process_with_planning()` method
   - Generate plan when task complexity exceeds threshold
   - Present plan to user for approval/refinement
   
3. **Plan generation improvements**:
   - Enhance `create_plan()` to generate meaningful steps
   - Use project context to suggest appropriate tools
   - Incorporate skill hints based on task type

### Phase 3: Plan-Execution Integration (Week 3)
**Objective**: Seamless workflow between planning and execution

1. **State transitions**:
   - `PLANNING` → `EXECUTING` → `MONITORING` → `ADAPTING`
   - Update `AgentFocus` enum with planning states
   
2. **Execution monitoring**:
   - Track plan step completion in real-time
   - Update plan status based on tool results
   - Detect stuck plans and trigger adaptation
   
3. **Plan adaptation**:
   - Modify plan when steps fail
   - Add/remove steps based on execution insights
   - Re-prioritize steps dynamically

### Phase 4: Advanced Features (Week 4)
**Objective**: Add polish and advanced capabilities

1. **Plan documentation**:
   - Generate markdown documentation for plans
   - Save plans with execution history
   - Create plan templates from successful executions
   
2. **Visualization and debugging**:
   - Console visualization of plan execution
   - Progress bars and status indicators
   - Plan debugging tools for development
   
3. **Integration with task tool**:
   - Use planning for subagent task delegation
   - Generate plans for complex sub-tasks
   - Monitor sub-task plan execution

## Technical Implementation Details

### Tool Implementation Pattern:

```python
class CreatePlanTool(Tool):
    def execute(self, goal: str, constraints: List[str] = None, ...) -> Dict[str, Any]:
        if not self.parent_agent or not hasattr(self.parent_agent, 'planning_engine'):
            return error_response("Planning not available")
        
        plan = self.parent_agent.planning_engine.create_plan(
            goal=goal,
            constraints=constraints,
            ...
        )
        
        return success_response({
            "plan_id": plan.id,
            "goal": plan.goal,
            "steps": len(plan.steps),
            "summary": self.parent_agent.planning_engine.get_plan_summary(plan)
        })
```

### Automatic Plan Detection Logic:

```python
def should_generate_plan(task_description: str, project_context: str) -> bool:
    # Complexity indicators
    complexity_keywords = [
        "implement", "refactor", "debug", "fix", "add", "create",
        "rewrite", "migrate", "optimize", "restructure"
    ]
    
    # Multi-step indicators
    step_indicators = ["then", "after", "first", "next", "finally", "step"]
    
    task_lower = task_description.lower()
    
    # Check for complexity
    keyword_count = sum(1 for kw in complexity_keywords if kw in task_lower)
    step_count = sum(1 for si in step_indicators if si in task_lower)
    
    # Check length as proxy for complexity
    word_count = len(task_description.split())
    
    return (keyword_count >= 2) or (step_count >= 2) or (word_count > 50)
```

### State Management Integration:

```python
class StateManager:
    def start_plan_execution(self, plan: Plan):
        self.state.active_plan = plan
        self.state.current_plan_step = plan.steps[0] if plan.steps else None
        self.set_focus(AgentFocus.EXECUTING)
        
    def update_plan_progress(self, step_id: str, status: PlanStepStatus, outcome: str):
        if self.state.active_plan:
            step = self.state.active_plan.get_step_by_id(step_id)
            if step:
                # Update step status
                # Check if plan complete
                # Trigger adaptation if needed
```

## Testing Strategy

### Unit Tests:
- Planning tool functionality
- Automatic plan detection heuristics
- State transitions during planning
- Plan adaptation logic

### Integration Tests:
- End-to-end planning workflow
- Tool integration with enhanced agent
- Plan execution monitoring
- Error handling and recovery

### User Tests:
- Natural language planning commands
- Plan visualization and monitoring
- Plan adaptation scenarios

## Success Metrics

1. **Usability**: Users can create and execute plans via natural language
2. **Efficiency**: Complex tasks completed faster with planning
3. **Reliability**: Plans adapt to obstacles and continue execution
4. **Transparency**: Users can monitor and understand plan execution

## Risks and Mitigations

### Risk 1: Over-planning for simple tasks
**Mitigation**: Set appropriate complexity thresholds, allow manual override

### Risk 2: Plan execution getting stuck
**Mitigation**: Timeout mechanisms, stuck detection, automatic adaptation

### Risk 3: Increased cognitive load for users
**Mitigation**: Clear plan visualization, optional automation, progressive disclosure

### Risk 4: Performance impact
**Mitigation**: Async plan generation, caching, incremental updates

## Timeline

- **Week 1**: Planning tools implementation and testing ✅ COMPLETED
- **Week 2**: Automatic plan detection and integration
- **Week 3**: Plan-execution workflow and adaptation
- **Week 4**: Advanced features and polish
- **Week 5**: Testing, documentation, and refinement

## Dependencies

1. Existing `PlanningEngine` stability (✅ Fixed in previous session)
2. Enhanced agent integration points (✅ Available)
3. Tool registry system (✅ Functional)
4. State management system (✅ Working)

## Next Steps

1. **COMPLETED**: Create planning tools module with basic implementations ✅
2. **COMPLETED**: Integrate tools into enhanced agent ✅
3. **Next**: Implement automatic plan detection (Phase 2)
4. **Future**: Add plan adaptation and advanced features (Phase 3-4)

This plan transforms Cortex from a reactive tool-execution agent to a proactive, goal-oriented planning agent capable of tackling complex multi-step tasks with structured approaches.