# Cortex Planning & Memory Enhancement Plan

## Executive Summary

This plan outlines how to enhance Cortex's planning and memory systems based on the goal-directed OS terminal agent mental model. The focus is on implementing a more sophisticated cognitive architecture that supports multi-step planning, layered memory, and adaptive reasoning.

## Current State Analysis

### Strengths
- **Basic ReAct loop**: Tool execution with observation feedback
- **Memory bank**: Tracks decisions, facts, and preferences
- **Conversation management**: Token-aware context management with summarization
- **Loop guards**: Basic error recovery and infinite loop prevention

### Gaps Identified
1. **No explicit goal decomposition**: Agent reasons step-by-step but lacks structured planning
2. **Monolithic memory**: Single memory bank without clear working/session/long-term separation
3. **Limited state management**: No explicit tracking of current goals, sub-goals, or progress
4. **No planning verification**: No systematic verification of plan execution results

## Proposed Architecture

Based on the mental model, we'll implement a **layered planning and memory system**:

```
┌─────────────────────────────────────────────────────┐
│                   Goal Layer                         │
│  • Primary goal (user intent)                       │
│  • Sub-goal decomposition                           │
│  • Goal dependencies and prioritization             │
└─────────────────────────────────────────────────────┘
                               │
┌─────────────────────────────────────────────────────┐
│                 Planning Layer                       │
│  • Task decomposition                               │
│  • Tool selection strategy                          │
│  • Execution planning with verification points      │
└─────────────────────────────────────────────────────┘
                               │
┌─────────────────────────────────────────────────────┐
│                 Execution Layer                      │
│  • ReAct loop (Reason → Act → Observe)              │
│  • Tool execution with state updates                │
│  • Progress tracking against plan                   │
└─────────────────────────────────────────────────────┘
                               │
┌─────────────────────────────────────────────────────┐
│                 Memory Layers                        │
│  ┌─────────────────┐ ┌─────────────────┐           │
│  │ Working Memory  │ │ Session Memory  │           │
│  │ • Current task  │ │ • Conversation  │           │
│  │ • File context  │ │ • Findings      │           │
│  │ • Tool state    │ │ • Failed        │           │
│  └─────────────────┘ │   approaches    │           │
│                      │ • Context       │           │
│                      │   assembled     │           │
│                      └─────────────────┘           │
│                               │                    │
│                      ┌─────────────────┐           │
│                      │ Long-term Memory│           │
│                      │ • Codebase      │           │
│                      │   structure     │           │
│                      │ • Learned       │           │
│                      │   patterns      │           │
│                      │ • Past solutions│           │
│                      └─────────────────┘           │
└─────────────────────────────────────────────────────┘
```

## Implementation Components

### Component 1: Enhanced Planning System

#### 1.1 Goal Manager
```python
class GoalManager:
    """Manages goals and sub-goals"""
    
    def __init__(self):
        self.primary_goal: Optional[str] = None
        self.sub_goals: List[SubGoal] = []
        self.current_goal_index: int = 0
        self.goal_dependencies: Dict[str, List[str]] = {}
        
    def decompose_goal(self, user_intent: str) -> List[SubGoal]:
        """Break down user intent into actionable sub-goals"""
        
    def prioritize_goals(self) -> None:
        """Reorder goals based on dependencies and urgency"""
        
    def update_progress(self, sub_goal_id: str, status: GoalStatus) -> None:
        """Track progress of individual sub-goals"""
```

#### 1.2 Plan Executor
```python
class PlanExecutor:
    """Executes plans with verification"""
    
    def create_plan(self, sub_goal: SubGoal) -> ExecutionPlan:
        """Create detailed execution plan for a sub-goal"""
        
    def execute_step(self, step: PlanStep) -> ExecutionResult:
        """Execute a single plan step"""
        
    def verify_result(self, step: PlanStep, result: Any) -> VerificationResult:
        """Verify if step execution achieved expected outcome"""
        
    def adapt_plan(self, failed_step: PlanStep, error: str) -> AdaptedPlan:
        """Adapt plan based on execution failures"""
```

### Component 2: Layered Memory Architecture

#### 2.1 Working Memory
```python
class WorkingMemory:
    """Short-term memory for current task"""
    
    def __init__(self):
        self.current_files: Set[str] = set()  # Files currently being examined
        self.tool_context: Dict[str, Any] = {}  # Context for current tool chain
        self.task_state: Dict[str, Any] = {}  # State of current task
        
    def update_file_context(self, file_path: str, content_summary: str) -> None:
        """Track which files are currently relevant"""
        
    def get_current_context(self) -> str:
        """Get summary of current working context"""
```

#### 2.2 Enhanced Memory Bank (Session Memory)
```python
class EnhancedMemoryBank(MemoryBank):
    """Extended memory bank with session memory capabilities"""
    
    def __init__(self, max_items: int = 100):
        super().__init__(max_items)
        self.session_facts: List[MemoryItem] = []  # Facts learned this session
        self.failed_approaches: List[FailedApproach] = []  # What didn't work
        self.successful_patterns: List[Pattern] = []  # What worked well
        
    def extract_learnings(self, tool_results: List[Dict]) -> None:
        """Extract learnings from tool execution results"""
        
    def get_session_summary(self) -> str:
        """Get comprehensive session summary for planning"""
```

#### 2.3 Long-term Memory Interface
```python
class LongTermMemoryInterface:
    """Interface to persistent memory (filesystem, database, etc.)"""
    
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.codebase_index: Optional[CodebaseIndex] = None
        
    def index_codebase(self) -> CodebaseIndex:
        """Create index of codebase structure and patterns"""
        
    def query_patterns(self, pattern_type: str) -> List[Pattern]:
        """Query for learned patterns"""
        
    def store_solution(self, problem: str, solution: str) -> None:
        """Store successful solutions for future reference"""
```

### Component 3: State Manager

#### 3.1 Agent State
```python
@dataclass
class AgentState:
    """Comprehensive agent state"""
    
    # Current focus
    current_goal: Optional[str] = None
    current_sub_goal: Optional[SubGoal] = None
    current_plan_step: Optional[PlanStep] = None
    
    # Context
    working_memory: WorkingMemory = field(default_factory=WorkingMemory)
    file_context: FileContext = field(default_factory=FileContext)
    
    # Progress
    completed_goals: List[str] = field(default_factory=list)
    failed_attempts: int = 0
    iteration_count: int = 0
    
    # Learning
    insights: List[Insight] = field(default_factory=list)
    patterns_recognized: List[Pattern] = field(default_factory=list)
```

#### 3.2 State Manager
```python
class StateManager:
    """Manages agent state across iterations"""
    
    def __init__(self):
        self.state = AgentState()
        self.state_history: List[AgentState] = []
        
    def update_state(self, 
                    tool_used: Optional[str] = None,
                    tool_result: Optional[Dict] = None,
                    new_goal: Optional[str] = None) -> None:
        """Update state based on latest actions"""
        
    def get_state_summary(self) -> str:
        """Get human-readable state summary"""
        
    def save_checkpoint(self) -> None:
        """Save current state as checkpoint"""
        
    def restore_checkpoint(self, checkpoint_id: str) -> None:
        """Restore state from checkpoint"""
```

### Component 4: Integration with Existing Cortex

#### 4.1 Enhanced System Prompt
Update the system prompt to include:
- Explicit planning guidance
- Memory layer awareness
- State management instructions

#### 4.2 Modified Agent Loop
```python
def enhanced_process_message(self, user_message: str):
    """Enhanced message processing with planning and memory"""
    
    # 1. Goal decomposition
    goals = self.goal_manager.decompose_goal(user_message)
    
    # 2. For each goal
    for goal in goals:
        # 3. Create execution plan
        plan = self.plan_executor.create_plan(goal)
        
        # 4. Execute plan with verification
        for step in plan.steps:
            # 5. Update working memory
            self.state_manager.update_working_context(step)
            
            # 6. Execute step
            result = self.plan_executor.execute_step(step)
            
            # 7. Verify result
            verification = self.plan_executor.verify_result(step, result)
            
            # 8. Adapt if needed
            if not verification.success:
                adapted_plan = self.plan_executor.adapt_plan(step, verification.error)
                # Continue with adapted plan
                
            # 9. Update session memory
            self.memory_bank.extract_learnings([result])
            
        # 10. Update goal progress
        self.goal_manager.update_progress(goal.id, GoalStatus.COMPLETED)
```

## Implementation Phases

### Phase 1: Foundation (Week 1)
1. **Create Goal Manager** - Basic goal decomposition and tracking
2. **Enhance Memory Bank** - Add session memory capabilities
3. **Create Working Memory** - Track current task context
4. **Update System Prompt** - Include planning and memory guidance

### Phase 2: Planning Integration (Week 2)
1. **Implement Plan Executor** - Basic plan creation and execution
2. **Create State Manager** - Track agent state across iterations
3. **Integrate with Agent Loop** - Modify `_process_message` to use planning
4. **Add Verification Logic** - Basic result verification

### Phase 3: Advanced Features (Week 3)
1. **Implement Adaptation Logic** - Plan adaptation based on failures
2. **Add Long-term Memory Interface** - Codebase indexing and pattern storage
3. **Enhance State Management** - Checkpoints and state restoration
4. **Add Planning Visualization** - Debug output for planning process

### Phase 4: Optimization & Testing (Week 4)
1. **Performance Optimization** - Minimize overhead of planning system
2. **Comprehensive Testing** - Test with various task types
3. **User Feedback Integration** - Gather and incorporate feedback
4. **Documentation** - Update docs with new planning capabilities

## Technical Specifications

### New Dependencies
- `networkx` (optional) - For goal dependency graphs
- `redis` (optional) - For persistent long-term memory storage

### File Structure Changes
```
cortex/
├── core/
│   ├── planning/
│   │   ├── __init__.py
│   │   ├── goals.py          # Goal Manager
│   │   ├── planner.py        # Plan Executor
│   │   └── verification.py   # Verification logic
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── working.py        # Working Memory
│   │   ├── session.py        # Enhanced Memory Bank
│   │   ├── long_term.py      # Long-term Memory Interface
│   │   └── state.py          # State Manager
│   └── conversation.py       # Updated with planning hooks
└── agent.py                  # Updated with enhanced processing
```

### Configuration Additions
```yaml
planning:
  enabled: true
  max_goals: 10
  enable_verification: true
  max_adaptations: 3
  
memory:
  working_max_items: 20
  session_max_items: 100
  long_term_enabled: false
  codebase_indexing: true
```

## Success Metrics

### Quantitative
- **Task completion rate**: Increase by 20%
- **Tool call efficiency**: Reduce redundant tool calls by 30%
- **Error recovery rate**: Improve from 60% to 85%
- **Context usage**: Reduce token usage by 25% through better memory management

### Qualitative
- **User satisfaction**: More coherent task execution
- **Debugging visibility**: Better understanding of agent's reasoning process
- **Adaptability**: Better handling of unexpected situations
- **Learning capability**: Improved retention of learned patterns

## Risks & Mitigations

### Risk 1: Performance Overhead
- **Mitigation**: Implement lazy evaluation and caching
- **Mitigation**: Make planning system opt-in via configuration

### Risk 2: Complexity Increase
- **Mitigation**: Gradual rollout with feature flags
- **Mitigation**: Comprehensive documentation and examples

### Risk 3: Integration Challenges
- **Mitigation**: Maintain backward compatibility
- **Mitigation**: Extensive testing with existing features

### Risk 4: User Experience Changes
- **Mitigation**: Provide clear migration guide
- **Mitigation**: Keep classic mode available

## Next Steps

1. **Review and approve** this plan
2. **Start Phase 1 implementation** (Goal Manager + Enhanced Memory)
3. **Create prototype** for initial validation
4. **Iterate based on feedback**

---

*This plan aligns Cortex with the goal-directed OS terminal agent mental model, providing a foundation for more sophisticated agent behavior while maintaining compatibility with existing features.*