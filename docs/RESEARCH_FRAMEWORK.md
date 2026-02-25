# Cortex Research Framework

The **Cortex Research Framework** is a systematic evaluation environment designed to measure the intelligence, resilience, and efficiency of the Cortex AI agent. It uses an isolated "sandbox" approach to put the agent through rigorous engineering challenges without risking the main codebase.

---

## 🔬 Core Objectives

1. **Quantify Intelligence**: Measure success rates across tiered engineering challenges of increasing complexity.
2. **Benchmark Resilience**: Evaluate how well the agent recovers from "environmental stress" (corrupted configs, missing dependencies, tool failures).
3. **Verify Metacognition**: Measure "Correction Latency"—the speed at which the agent's internal monologue identifies and fixes its own mistakes.
4. **Optimize Efficiency**: Track token usage and tool-call counts to ensure the agent remains performant.

---

## 🏗️ Architecture

The framework operates through four primary layers:

### 1. The Sandbox Provider (`research/orchestrator.py`)
To ensure safety and reproducibility, the framework clones the entire project into a temporary directory (sandbox). All agent operations, file edits, and command executions happen within this isolated clone.

### 2. Challenge Bank (`research/challenges.py`)
A collection of `ResearchChallenge` objects. Each challenge defines:
- **Goal**: A natural language instruction for the agent.
- **Complexity**: A 1-10 rating of the difficulty.
- **Verification Script**: A shell command (e.g., `pytest`, `mypy`) that determines if the agent actually solved the problem.

### 3. Evaluation Tiers
The `ResearchOrchestrator` runs the same challenges across different "brain" configurations:
- **Control**: Baseline configuration (no layered memory or metacognition).
- **Architectural**: Enables the Metacognitive Core (confidence tracking, tone, monologue).
- **Specialized/Stress**: Full suite enabled + intentional environment corruption.

### 4. Metrics & Reporting (`research/metrics.py`)
The framework generates JSON and Markdown reports in `research/reports/`, tracking:
- **Success Rate**: % of challenges passed.
- **Turns Taken**: Number of tool calls required.
- **Correction Latency**: Steps between first failure and final success.
- **Token Efficiency**: Tokens consumed per successful task.

---

## 🚀 Setup & Installation

### 1. Prerequisites
Ensure you have the core Cortex development environment installed:
```bash
pip install -e ".[dev]"
```

### 2. Environment Variables
The research framework defaults to specific models for benchmarking. Ensure your `.env` file has the necessary API keys:
```bash
# Recommended for research due to context window and reasoning
OPENROUTER_API_KEY=your_key_here
```

### 3. Verification Tools
Many challenges rely on `mypy` and `pytest` for verification. Install these via:
```bash
pip install mypy pytest
```

---

## 🛠️ How to Run Research

### Basic Run
To execute the default research suite (currently configured in `run_research.py`):
```bash
python run_research.py
```

### Customizing the Run
You can modify `run_research.py` to target specific models or tiers:
```python
# Edit run_research.py
model = "anthropic/claude-3.5-sonnet"
orchestrator = ResearchOrchestrator(model, base_dir)

# Uncomment tiers to run
orchestrator.run_tier("Control", CHALLENGES)
orchestrator.run_tier("Architectural", CHALLENGES)
orchestrator.run_tier("Stress", STRESS_CHALLENGES)
```

---

## 📊 Interpreting Reports

Reports are saved in `research/reports/report_[TIMESTAMP].json`. A typical scorecard looks like this:

| Metric | Control | Architectural | Stress |
|--------|---------|---------------|--------|
| Success Rate | 60% | 85% | 70% |
| Avg. Turns | 12.4 | 8.2 | 14.1 |
| Correction Latency | 3.2 | 1.1 | 2.4 |

**A "Win" in research is defined as:**
1. Higher success rate in the **Stress** tier.
2. Lower **Correction Latency** (indicating the Metacognitive Core is working).
3. Fewer **Avg. Turns** for the same challenge.

---

## 🧪 Adding New Challenges

To add a test case, edit `research/challenges.py`:
```python
ResearchChallenge(
    id="C06",
    name="Feature Name",
    description="Instruct the agent to do X...",
    target_files=["path/to/file.py"],
    success_criteria="What success looks like",
    complexity=5,
    verification_script="pytest tests/new_feature_test.py"
)
```
