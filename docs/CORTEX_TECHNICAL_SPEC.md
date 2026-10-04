# Cortex: Technical Specification

This describes how Cortex works today. Where a feature is optional, experimental or limited, it
says so; [STATUS.md](STATUS.md) has the one-page summary and [SECURITY.md](SECURITY.md) has the
safety model in full.

## 1. Architecture

```
  CLI / REPL  (cortex/cli.py, cortex/cli_commands/, cortex/ui/)
        │
  Agent loop  (cortex/agent.py): one user request = one turn
        │
  ┌─────┴───────────────────────────────────────────────────────────────┐
  │ Permissions   core/agent_permissions.py, tool_policy.py, security.py │
  │ Undo          core/transaction.py (files), core/checkpoints.py (git)  │
  │ Memory        core/memory/, core/memory_layers/                       │
  │ Planning      core/planning.py        Prompts   core/prompts/         │
  │ Providers     core/providers/         Hooks     hooks/                │
  └─────┬───────────────────────────────────────────────────────────────┘
        │
  Tools  (cortex/tools/): files, edit, git, search, AST, web, commands, tests, plan, memory
        │
  Your project, your git repository, and the model provider
```

There is no server, API gateway or MCP endpoint: Cortex is a client that runs in your terminal.

## 2. The agent loop

`Cortex._process_message(text)` runs one **turn**:

1. Open a transaction and mark a git checkpoint as due (see §6).
2. Add the user message; refresh the system prompt; ask the model.
3. If the model asked for tools, run them (in parallel when they are independent), append each
   result directly after the request that produced it, and loop.
4. Stop when the model answers without tool calls, the iteration limit is reached, the loop guard
   fires, a hook blocks the prompt, or shutdown is requested.

The turn returns a `TurnResult` (`cortex/core/turn.py`) with a `status` of `ok`, `error`,
`max_iterations`, `loop_guard`, `blocked` or `interrupted`, plus the iteration and tool-call
counts and any error. One-shot mode (`cortex -p`) exits 0 only for `ok`; the gym, subagents and
the benchmark read the same result instead of guessing from printed output.

**Loop guard** (`core/loop_guards.py`): fed with every tool call and every error; stops a turn
when the same call or error repeats, and is reset at the start of each turn.

## 3. Messages and providers

Chat APIs require that an assistant message with tool calls is *immediately* followed by one
`tool` message per call. Anything that edits history can break that, so
`cortex/utils/message_validation.py` detects violations, repairs them (moves results back, adds a
placeholder for a missing one, drops orphans) and trims or summarises history without splitting a
tool exchange (`tail_start`). Before each model call the agent validates the messages; with
`CORTEX_STRICT_MESSAGES=1` (used by the tests) a violation raises instead of being repaired.

Providers (`core/providers/`): OpenRouter (default), Anthropic, DeepSeek, Ollama, and an
OpenAI-compatible provider for OpenAI and local servers (vLLM, llama.cpp, LM Studio), chosen only
with `--provider openai` because a model name cannot tell such a server from OpenRouter. Each
returns `{"message": ..., "usage": {"input_tokens", "output_tokens"}}`; `usage` is omitted when the
API reported none (`providers/usage.py`). A provider that fixes the model's context window
exposes it as `context_window`, which the agent uses to size the history; the OpenAI-compatible
provider knows it only when configured.

Ollama is always sent an explicit context window (`options.num_ctx`: 32,768 by default,
`ollama.num_ctx` or `CORTEX_OLLAMA_NUM_CTX` to change it), because its own default is smaller
than Cortex's tool definitions and system prompt and would silently truncate them. A provider
that fixes a window reports it as `context_window`, and the agent limits its history budget to
that window minus the tool definitions (`ConversationManager.limit_context`), warning when too
little is left.

### The system prompt

Built by `PromptBuilder` in two parts so provider prompt caches (which match on the start of the
prompt) stay valid: first everything fixed for the session (identity, tool documentation,
planning and memory guidance, project context, custom instructions), then what changes
(retrieved memory for the current request, session memory, current state, and the experimental
metacognition note), slowest-changing first. Long-term memory is looked up once per user message,
not once per loop iteration.

## 4. Tools and the tool policy

Every registered tool has a class in `core/tool_policy.py`: `read_only`, `agent_state` (the
agent's own bookkeeping: todos, plans, memory), `mutating` or `runs_code`. A test fails if a
registered tool has none. File tools check that paths stay inside the project directory.

`remember`, `create_and_execute_plan` and friends are tools like any other; the planning tools
are only offered with `--planning`.

## 5. Permissions

- **NORMAL**: each tool that writes, edits, runs a command or changes git asks first.
- **PLAN**: `allowed_in_plan_mode` lets only `read_only` and `agent_state` tools through; an
  unclassified tool is refused, so a new tool is blocked until someone classifies it.
- **AUTO_APPROVE**: no prompts.
- **Command blocklist** (`core/security.py:is_dangerous_command`), applied in every mode: splits a
  command line into the commands that will run (`;`, `&&`, `||`, `|`, newlines), unwraps `sudo`,
  `env`, `xargs` and `sh -c '...'`, and refuses the well-known destructive forms. It is a filter,
  not a boundary.
- **Command sandbox** (`core/command_sandbox.py`): optional bubblewrap confinement of
  `execute_command` and `run_tests`; refused, never skipped, if requested and unavailable.

## 6. Undo

Two layers, because they see different things:

- **Transactions** (`core/transaction.py`): one `TransactionManager` per session, passed to every
  tool. Each user request opens a transaction; every file a tool creates or changes is backed up
  first as exact bytes; the transaction stays open after the turn so `/rollback` can restore it,
  and is committed when the next request starts or the session ends.
- **Git checkpoints** (`core/checkpoints.py`): before the first tool of a request that could
  change anything (including shell commands), a snapshot of the whole working tree is committed
  to a private ref `refs/cortex/<session>/<n>`, built with a temporary index so HEAD, branches,
  the real index and stashes are untouched. `/undo` restores the files that differ and removes
  files created since; `/redo` reverses an undo. Git-ignored files and branch moves are not
  covered. Checkpoints are removed when the session ends; stale ones are swept after 7 days.

## 7. Memory

- **Session memory** (`--memory`): working memory (current task, files, tools), failed approaches
  (the same failure is counted, not listed again) and successful patterns, kept for the session.
- **Long-term memory** (`[memory]` extra, `semantic_memory.enabled: true`): a ChromaDB vector
  store under `.cortex/semantic_db`.
  - **Contract** (`core/memory/contract.py`): stores decisions, conventions/preferences, explicit
    facts, summaries of solved problems and anything explicitly remembered. It does not store the
    user's requests, raw errors, file references or progress notes.
  - **De-duplication**: an entry's id is a hash of its normalised text, so writing a fact twice
    leaves one record that keeps its creation time, counts the sighting and keeps the higher
    confidence.
  - **Ranking** (`core/memory/semantic.py`): score = 0.6 x similarity + 0.2 x confidence +
    0.2 x recency, where recency halves every 30 days since the entry was last confirmed
    (explicit user instructions do not fade). Computed when reading; nothing is written back.
    Confirming an entry (`verify`) raises its confidence and restarts its age; a contradiction
    lowers it.
  - **Retrieval**: memories less similar to the request than `semantic_memory.min_similarity`
    (default 0.3, a starting value) are not put in the prompt.
  - **Control**: the `remember` tool; `/memory list`, `add`, `edit`, `delete`, `search`, `clear`.

## 8. Planning (`--planning`)

The model supplies the steps (`create_and_execute_plan` requires them) and `core/planning.py`
runs them one at a time. A step that fails or is blocked fails the plan, and the result carries
per-step summaries. `SUBTASK`, `DECISION` and `CHECKPOINT` steps are not implemented and are
reported as not implemented. There is no replanning.

## 9. Metacognition (`--metacognition`, experimental)

`MetacognitiveState` holds confidence, urgency and an emotional tone updated by fixed rules after
each tool result (mood follows *consecutive* failures: one is "cautious", two in a row are
"frustrated", a success resets the streak). When the flag is on, a short note is added to the
prompt. Off by default; nothing measures whether it helps.

## 10. Practice and measurement

- **Benchmark** (`bench/`, [BENCHMARK.md](BENCHMARK.md)): 20 tasks judged by their own tests.
- **Cognitive Gym** (`core/gym/`): the agent works in a scratch copy of a project. With a
  verifier (`/gym --bench <task>`) the result is the verifier's verdict; without one the outcome
  is reported as unchecked.

## 11. Configuration

Priority, lowest to highest: built-in defaults, a YAML file (`--config`), `CORTEX_*` environment
variables, command-line flags. Every key in the YAML file is applied (a test fails when a setting
is added without one proving it takes effect). Main sections: `model`, `provider`,
`permission_mode`, `max_iterations`, `transactions`, `checkpoints`, `command_sandbox`,
`semantic_memory`, `session_retention`, `timeouts`, `hooks`, `routing`, `parallel_execution`.

## 12. Storage

`~/.cortex/sessions/` (saved conversations), `~/.cortex/backups/` (file backups while a request
is open), `.cortex/semantic_db/` (long-term memory, if enabled), `refs/cortex/*` in your git
repository (checkpoints, while the session runs). Session files are written atomically.

## 13. Testing

The suite is offline and hermetic (no network, no model, a throwaway git identity, a stub for the
embedding model). `tests/e2e/` drives the real agent loop with a scripted fake provider
(`tests/e2e/scripted.py`); its `KNOWN_BUGS` registry holds open bugs as strict expected failures.
CI runs the suite on Linux, Windows and macOS with Python 3.9 to 3.12, lint, a blocking type
check on the modules listed in `pyproject.toml`, the benchmark's self-check, the Rust and Go
tests, a Docker build, and a security scan. Test counts and coverage are generated by CI.

## 14. Known gaps

Planning is sequential and cannot replan; long-term memory's benefit is unmeasured; the three
optional agent features have no ablation yet; the Rust AST parser is unused; the Go services have
no client; model routing and delegation have not been audited; most of `cortex/` is not in the
blocking type check.
