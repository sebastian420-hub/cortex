# System Prompt Future Work Plan

## Executive Summary

This document outlines a comprehensive 6-month roadmap for enhancing Cortex's system prompt capabilities. The plan focuses on externalization, testing, optimization, and user customization while maintaining backward compatibility.

---

## Phase 1: Externalization & Configuration (Month 1-2)

### 1.1 Configuration-Based Prompt Management
**Goal**: Move system prompts from code to configuration files for easier customization.

#### Deliverables:
1. **Prompt Configuration Schema** (`config/prompt_schema.yaml`)
   - Define structured schema for prompt components
   - Support for variables, conditions, and imports
   - Validation rules for required sections

2. **Prompt Manager Module** (`cortex/core/prompt_manager.py`)
   ```python
   class PromptManager:
       def __init__(self, config_path: Path):
           self.config = self._load_prompt_config(config_path)
           self.templates = self._load_templates()
       
       def generate_prompt(
           self, 
           agent_type: str = "standard",
           context: Dict[str, Any] = None
       ) -> str:
           """Generate prompt from template with context"""
       
       def update_dynamic_prompt(
           self,
           conversation: ConversationManager,
           updates: Dict[str, Any]
       ) -> None:
           """Update conversation with new prompt"""
   ```

3. **Prompt Configuration Files**
   - `config/prompts/standard.yaml` - Base agent prompt
   - `config/prompts/enhanced.yaml` - Enhanced agent with planning
   - `config/prompts/security.yaml` - Security agent prompt
   - `config/prompts/minimal.yaml` - Token-optimized version

#### Success Criteria:
- ✅ 90% of prompt content externalized to config files
- ✅ No breaking changes to existing agent initialization
- ✅ All existing tests pass with new configuration system
- ✅ Configuration validation with helpful error messages

### 1.2 Environment-Based Prompt Selection
**Goal**: Allow users to select prompts via environment variables or CLI flags.

#### Features:
- `CORTEX_PROMPT=minimal` - Use minimal prompt
- `CORTEX_PROMPT=enhanced` - Use enhanced prompt with planning
- `--prompt-profile` CLI flag for one-shot usage
- Project-specific `.cortex/prompt.yaml` auto-detection

#### Implementation:
```python
# In config.py
class PromptConfig:
    profile: str = "standard"  # standard, enhanced, security, minimal, custom
    custom_path: Optional[Path] = None
    variables: Dict[str, Any] = {}  # Custom variables to inject
    
    @classmethod
    def from_project(cls, project_dir: Path) -> "PromptConfig":
        """Auto-detect project-specific prompt config"""
```

---

## Phase 2: Testing & Validation Framework (Month 2-3)

### 2.1 Prompt Testing Framework
**Goal**: Create comprehensive testing for prompt generation and validation.

#### Deliverables:
1. **Prompt Test Suite** (`tests/test_prompts/`)
   - Unit tests for each prompt component
   - Integration tests for full prompt generation
   - Provider-specific prompt format tests

2. **Prompt Validation Tool** (`scripts/validate_prompt.py`)
   ```bash
   # Validate a prompt configuration
   python scripts/validate_prompt.py config/prompts/standard.yaml
   
   # Test token counts
   python scripts/validate_prompt.py --tokens config/prompts/standard.yaml
   
   # Check for missing variables
   python scripts/validate_prompt.py --check-variables config/prompts/standard.yaml
   ```

3. **Golden Tests** for Prompt Outputs
   - Store expected prompt outputs for regression testing
   - Automatically update golden tests when prompts change
   - Compare token counts against thresholds

#### Test Coverage Goals:
- 95%+ line coverage for prompt generation code
- 100% of configuration options tested
- All provider-specific formats validated
- Performance benchmarks for generation speed

### 2.2 A/B Testing Infrastructure
**Goal**: Enable controlled experiments with different prompt variations.

#### Features:
1. **Experiment Manager** (`cortex/experiments/prompt_experiments.py`)
   ```python
   class PromptExperiment:
       def __init__(self, variations: List[PromptVariation]):
           self.variations = variations
           self.metrics = ExperimentMetrics()
       
       def run_task(self, task_description: str) -> Dict[str, Any]:
           """Run task with different prompt variations"""
       
       def collect_metrics(self) -> ExperimentResults:
           """Collect and analyze results"""
   ```

2. **Standardized Test Tasks**
   - Code understanding tasks
   - Bug fixing scenarios
   - Feature implementation challenges
   - Documentation generation

3. **Metrics Collection**
   - Success rate by prompt variation
   - Token usage efficiency
   - Tool call patterns
   - User satisfaction (if available)

---

## Phase 3: Performance Optimization (Month 3-4)

### 3.1 Token Optimization Engine
**Goal**: Automated analysis and optimization of prompt token usage.

#### Deliverables:
1. **Token Analyzer** (`cortex/optimization/token_analyzer.py`)
   ```python
   class TokenAnalyzer:
       def analyze_prompt(self, prompt: str) -> TokenAnalysis:
           """Analyze token usage by section"""
       
       def suggest_optimizations(self, analysis: TokenAnalysis) -> List[Optimization]:
           """Suggest specific optimizations"""
       
       def apply_optimizations(self, prompt: str, optimizations: List[Optimization]) -> str:
           """Apply optimizations to prompt"""
   ```

2. **Optimization Strategies**
   - **Compression**: Remove redundant phrasing
   - **Restructuring**: Reorganize for better comprehension
   - **Abstraction**: Move details to help system
   - **Variable Injection**: Dynamic content insertion

3. **Benchmark Suite**
   - Standardized prompts for comparison
   - Performance metrics tracking
   - Regression detection

### 3.2 Caching & Memoization
**Goal**: Reduce prompt generation overhead for repeated operations.

#### Implementation:
```python
class PromptCache:
    def __init__(self, max_size: int = 100):
        self.cache = LRUCache(max_size)
        self.hits = 0
        self.misses = 0
    
    def get_prompt(
        self,
        agent_type: str,
        context_hash: str,
        generate_fn: Callable[[], str]
    ) -> str:
        """Get cached prompt or generate new one"""
    
    def clear_expired(self, max_age_seconds: int = 3600):
        """Clear old cache entries"""
```

#### Performance Targets:
- 50%+ cache hit rate for typical usage
- <10ms prompt generation time (cached)
- <50ms prompt generation time (uncached)
- Memory usage < 10MB for cache

---

## Phase 4: User Customization & Personalization (Month 4-5)

### 4.1 User Prompt Customization
**Goal**: Allow users to customize prompts without modifying code.

#### Features:
1. **User Prompt Directory** (`~/.config/cortex/prompts/`)
   - User can create custom prompt templates
   - Inherit from base templates
   - Override specific sections

2. **Prompt Builder CLI Tool**
   ```bash
   # Interactive prompt builder
   cortex prompt build
   
   # Create from template
   cortex prompt create --template=standard --output=my-custom-prompt.yaml
   
   # Validate custom prompt
   cortex prompt validate my-custom-prompt.yaml
   ```

3. **Template Inheritance System**
   ```yaml
   # my-custom-prompt.yaml
   extends: standard
   modifications:
     - section: "Efficiency Patterns"
       action: "append"
       content: |
         ## My Custom Pattern
         - Always check for tests before modifying critical code
     - section: "Response Style"
       action: "replace"
       content: |
         - Be extremely concise
         - Use bullet points when possible
   ```

### 4.2 Project-Specific Prompts
**Goal**: Auto-detect and apply project-specific prompt optimizations.

#### Auto-Detection Rules:
1. **Project Type Detection** (already implemented in help system)
   - Python, JavaScript, Rust, Go, etc.
2. **Framework Detection**
   - Django, React, Rails, etc.
3. **Project Size Categories**
   - Small (< 10 files)
   - Medium (10-100 files)
   - Large (100+ files)

#### Implementation:
```python
class ProjectAwarePrompt:
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.analyzer = ProjectAnalyzer(project_dir)
    
    def get_optimized_prompt(self) -> str:
        """Get prompt optimized for this project"""
        project_type = self.analyzer.detect_project_type()
        framework = self.analyzer.detect_framework()
        size_category = self.analyzer.get_size_category()
        
        return self._generate_prompt(project_type, framework, size_category)
```

---

## Phase 5: Monitoring & Analytics (Month 5-6)

### 5.1 Prompt Effectiveness Tracking
**Goal**: Collect metrics on prompt performance and effectiveness.

#### Metrics to Track:
1. **Operational Metrics**
   - Prompt generation time
   - Token counts per section
   - Cache hit/miss rates
   
2. **Effectiveness Metrics**
   - Task completion rate by prompt variant
   - Average iterations to solution
   - Tool usage patterns
   - Error rates

3. **User Interaction Metrics**
   - User corrections required
   - Clarification questions asked
   - Satisfaction indicators (if available)

#### Implementation:
```python
class PromptMetricsCollector:
    def __init__(self):
        self.metrics_buffer = []
        self.aggregated_metrics = {}
    
    def record_prompt_usage(
        self,
        prompt_id: str,
        context: Dict[str, Any],
        outcome: Optional[Dict[str, Any]] = None
    ):
        """Record prompt usage and outcome"""
    
    def generate_report(self, period: str = "daily") -> MetricsReport:
        """Generate analytics report"""
```

### 5.2 Anomaly Detection
**Goal**: Detect when prompts are performing poorly or behaving unexpectedly.

#### Detection Rules:
1. **Token Usage Spikes**
   - Sudden increase in prompt tokens
   - Unexpectedly long generated prompts

2. **Performance Degradation**
   - Slower task completion
   - Increased error rates
   - More clarification questions

3. **Behavioral Changes**
   - Different tool usage patterns
   - Changed response styles
   - Unusual error messages

#### Alerting System:
```python
class PromptAnomalyDetector:
    def __init__(self, baseline_metrics: Dict[str, Any]):
        self.baseline = baseline_metrics
        self.alerts = []
    
    def check_anomalies(self, current_metrics: Dict[str, Any]) -> List[AnomalyAlert]:
        """Check for anomalies against baseline"""
    
    def send_alert(self, alert: AnomalyAlert):
        """Send alert via configured channels (log, email, etc.)"""
```

---

## Phase 6: Advanced Features & Integration (Month 6+)

### 6.1 Multi-Modal Prompt Support
**Goal**: Support prompts that incorporate images, code snippets, or other media.

#### Features:
1. **Embedded Content Support**
   - Inline code examples
   - Reference images/diagrams
   - Structured data tables

2. **Context-Aware Insertion**
   - Automatically include relevant code snippets
   - Add project structure diagrams
   - Inject dependency graphs

### 6.2 Dynamic Prompt Adjustment
**Goal**: Adjust prompts based on conversation history and context.

#### Implementation:
```python
class AdaptivePromptManager:
    def __init__(self, base_prompt: str):
        self.base_prompt = base_prompt
        self.context_history = []
    
    def adapt_for_context(
        self,
        conversation_history: List[Dict[str, Any]],
        current_focus: Optional[str] = None
    ) -> str:
        """Adapt prompt based on conversation context"""
        
        # Extract key topics from history
        topics = self._extract_topics(conversation_history)
        
        # Adjust emphasis based on current focus
        adjusted_prompt = self._adjust_emphasis(self.base_prompt, topics, current_focus)
        
        return adjusted_prompt
```

### 6.3 Prompt Versioning & Migration
**Goal**: Manage prompt versions and migrations for backward compatibility.

#### Features:
1. **Semantic Versioning for Prompts**
   - `prompt-v1.2.3.yaml`
   - Breaking changes require major version bump
   
2. **Migration Assistant**
   ```bash
   # Check for needed migrations
   cortex prompt migrate --check
   
   # Apply migrations
   cortex prompt migrate --apply
   
   # Create migration script
   cortex prompt migrate --create v1.2.3 v1.3.0
   ```

3. **Compatibility Layer**
   - Support multiple prompt versions simultaneously
   - Automatic translation between versions
   - Deprecation warnings for old versions

### 6.4 Plan Documentation Integration
**Goal**: Automatically generate documentation for every plan created by the agent, providing transparency and audit trails.

#### Features:
1. **Automatic Documentation Generation**
   - Generate markdown documentation when plans are created
   - Update documentation with execution results
   - Store in `.cortex/plans/` directory with plan IDs

2. **Documentation Content**
   - Plan metadata (goal, description, timestamps)
   - Step-by-step execution with status and outcomes
   - Success criteria and constraints
   - Reflections and learnings from execution

3. **System Prompt Integration**
   - Enhance system prompt to include documentation guidance
   - Add instructions for documenting plans and outcomes
   - Include examples of good documentation practices

4. **Configuration Options**
   - Enable/disable plan documentation
   - Choose output format (markdown, JSON, both)
   - Custom templates for documentation

#### Implementation:
```python
class PlanDocumentationGenerator:
    """Generate human-readable documentation for plans."""
    
    def generate_markdown(self, plan: Plan, 
                         execution_result: Optional[Dict[str, Any]] = None) -> str:
        # Generate comprehensive markdown documentation
        return markdown_content
```

#### System Prompt Enhancement:
Add to enhanced system prompt:
```
## Documentation Responsibility
- Document every plan you create in `.cortex/plans/{plan_id}.md`
- Include goal, steps, outcomes, and learnings
- Update documentation after plan execution
- Use clear, structured markdown format
```

---

---

## Implementation Priorities

### Priority 1 (High Impact, Low Effort)
1. **Externalization** (Phase 1.1) - Immediate value, foundation for other work
2. **Testing Framework** (Phase 2.1) - Essential for maintaining quality
3. **Token Optimization** (Phase 3.1) - Direct performance improvement

### Priority 2 (Medium Impact, Medium Effort)
1. **User Customization** (Phase 4.1) - User experience improvement
2. **Caching System** (Phase 3.2) - Performance optimization
3. **Project Detection** (Phase 4.2) - Context-aware improvements

### Priority 3 (Strategic, Higher Effort)
1. **A/B Testing** (Phase 2.2) - Data-driven improvements
2. **Monitoring** (Phase 5) - Long-term quality maintenance
3. **Adaptive Prompts** (Phase 6.2) - Advanced intelligence

---

## Success Metrics

### Quantitative Metrics
1. **Performance**
   - Prompt generation time: < 50ms (p95)
   - Cache hit rate: > 50%
   - Memory usage: < 20MB for prompt system

2. **Quality**
   - Test coverage: > 90%
   - Regression test failures: 0
   - User-reported prompt issues: < 1 per month

3. **Efficiency**
   - Average token count reduction: 20% from baseline
   - Task completion iterations: 15% reduction
   - Tool call efficiency: 10% improvement

### Qualitative Metrics
1. **User Satisfaction**
   - Customization options satisfaction
   - Ease of prompt modification
   - Documentation clarity

2. **Developer Experience**
   - API simplicity and consistency
   - Error message helpfulness
   - Migration ease

---

## Risks & Mitigations

### Technical Risks
1. **Breaking Changes**
   - **Mitigation**: Maintain backward compatibility layer
   - **Mitigation**: Provide migration tools and documentation

2. **Performance Overhead**
   - **Mitigation**: Implement caching and lazy loading
   - **Mitigation**: Profile and optimize critical paths

3. **Configuration Complexity**
   - **Mitigation**: Provide sensible defaults
   - **Mitigation**: Create configuration validation and helpful errors

### Organizational Risks
1. **Development Time**
   - **Mitigation**: Phased implementation with incremental value
   - **Mitigation**: Prioritize based on impact/effort ratio

2. **User Adoption**
   - **Mitigation**: Maintain existing workflows by default
   - **Mitigation**: Provide clear upgrade paths and benefits

---

## Resource Requirements

### Development Team
- **1 Senior Backend Engineer**: Architecture and core implementation
- **1 Full Stack Engineer**: CLI tools and user interfaces
- **0.5 DevOps Engineer**: Monitoring and deployment support
- **0.5 QA Engineer**: Testing framework and validation

### Timeline
- **Phase 1-2**: Months 1-3 (Foundation)
- **Phase 3-4**: Months 4-5 (Optimization & Customization)
- **Phase 5-6**: Months 6+ (Advanced Features)

### Infrastructure
- **Storage**: 1GB for prompt configurations and caching
- **Monitoring**: Integration with existing monitoring stack
- **CI/CD**: Enhanced testing pipeline for prompt validation

---

## Conclusion

This 6-month roadmap provides a structured approach to evolving Cortex's system prompt capabilities from a hardcoded implementation to a sophisticated, configurable, and intelligent system. By following this plan, we can achieve:

1. **Greater Flexibility**: Users can customize prompts for their specific needs
2. **Improved Performance**: Optimized token usage and faster generation
3. **Better Quality**: Comprehensive testing and validation
4. **Data-Driven Improvements**: A/B testing and metrics collection
5. **Future-Proof Architecture**: Extensible design for new features

The implementation should follow an iterative approach, with each phase delivering measurable value while building toward the long-term vision of intelligent, adaptive prompting system.