# Cortex Cognitive Gym: Implementation Plan
## Autonomous Learning via Synthetic Experience

### 1. Vision
To transition Cortex from a "static tool" to a "learning agent" that improves through self-simulation. The agent will run in isolated sandboxes ("Gyms"), encounter engineered challenges, and store both successful strategies and failure analysis in its Semantic Memory (Vector DB).

### 2. Architecture: The Experience Loop
1. **Sandbox Creation:** Snapshot the current project state.
2. **Challenge Injection:** Programmatically introduce a problem (e.g., break a test, introduce a circular import).
3. **Autonomous Execution:** The agent attempts to solve the task using the **Metacognitive Core**.
4. **Appraisal & Reflection:** Post-task, the agent performs a "Metacognitive Review" of its performance.
5. **Semantic Storage:** "Synthetic Experiences" are indexed in ChromaDB with high priority.
6. **Replay Retrieval:** Real-world tasks trigger retrieval of these synthetic experiences.

---

### 3. Implementation Components

#### A. The `GymManager` (New Module: `cortex/core/gym/manager.py`)
- **Workspace Isolation:** Uses `shutil` and temporary directories to create safe "Practice Sandboxes."
- **State Snapshots:** Leverages `CheckpointManager` to restore environments after training runs.
- **Goal Generator:** A set of predefined "Engineering Kata" (e.g., "Fix broken pytest," "Refactor this class to use Composition over Inheritance").

#### B. The `ExperienceExtractor` (Enhancement to `cortex/core/memory_layers/session.py`)
- Converts raw tool traces into "Synthetic Experiences."
- **Structure:**
  ```json
  {
    "task": "Fix Circular Import",
    "success": true,
    "key_insight": "Found that moving imports inside functions is a temporary fix but moving to a new 'types.py' is permanent.",
    "failed_attempts": ["Tried moving import to bottom of file (Syntax Error)"],
    "monologue_trace": ["I was frustrated initially but found a pattern in the AST."]
  }
  ```

#### C. `TrainingMode` (State Management)
- A new `AgentFocus.TRAINING` state in `StateManager`.
- When in Training Mode, the `PromptBuilder` provides "Learning-First" instructions, encouraging the agent to take risks and explore multiple solutions.

---

### 4. Roadmap

#### Phase 1: The Infrastructure (Days 1-2)
- Create `cortex/core/gym/` directory.
- Implement `SandboxProvider` for filesystem isolation.
- Add `AgentFocus.TRAINING` to `StateManager`.

#### Phase 2: The Learning Loop (Days 3-4)
- Implement `MetacognitiveReflector` - a specialized tool that asks the LLM to summarize its session into a "Synthetic Experience" document.
- Update `EnhancedMemoryBank` to specifically tag these experiences as `source="synthetic"`.

#### Phase 3: The Gym CLI (Day 5)
- Add a new command: `cortex gym --task <task_name>`.
- Allow users to "train" their agent on a specific directory.
- Implement "Bulk Training" where the agent runs 5 variations of a problem to find the most robust pattern.

---

### 5. Technical Challenges & Mitigations
- **Hallucination in Memory:** *Mitigation:* Only store experiences if the final state passes `pytest` or `ruff` checks.
- **Resource Exhaustion:** *Mitigation:* Training runs have strict `max_iterations` and token limits.
- **Vector DB Overload:** *Mitigation:* Use an "Importance Score" (0-1) calculated by the Metacognitive Core to prune low-value experiences.

---

### 6. Expected Outcome
Cortex will no longer be limited to its training cutoff. If a new library (like `Tailwind v4` or a new `Pydantic` version) is released, the user can let Cortex "play" in a sandbox with the library for 10 minutes. By the end, Cortex will have "Learned" the new patterns and stored them in its own brain, ready for production work.
