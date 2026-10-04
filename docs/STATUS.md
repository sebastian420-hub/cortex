# What works and what does not

This page says, area by area, what Cortex does today, how that is checked, and where it falls
short. It contains no test counts or coverage figures: CI generates those on every run (see the
badges in the [README](../README.md)), so they cannot go stale here.

**Reading the status column**

- **Works**: exercised end to end by tests that drive the real agent loop.
- **Works, with limits**: does what is described, and the limits are listed.
- **Experimental**: exists, is off by default, and nothing measures whether it helps.
- **Optional**: built and tested separately; not used unless you set it up.
- **Not implemented**: described in older documents; there is no code for it.

## The agent

| Area | Status | How it is checked, and the limits |
|------|--------|-----------------------------------|
| Agent loop with file, git, search, AST and web tools, hooks, and five providers (OpenRouter, Anthropic, DeepSeek, Ollama, OpenAI-compatible) | Works | `tests/e2e/test_invariants.py` drives the loop with a scripted model. Provider code is tested with fake clients, not live APIs |
| Valid conversation: every tool request is followed by its result, even after truncation or summarisation | Works | `tests/unit/utils/test_message_validation.py` and the e2e tests; strict providers reject a broken order, so a repair step exists as a safety net |
| A turn ends with a result (`ok`, `error`, `max_iterations`, `loop_guard`, `blocked`, `interrupted`); one-shot mode exits non-zero unless it is `ok` | Works | e2e tests. The exit code says the turn finished, not that the work is right |
| Loop guard (stops after the same error repeats) | Works | `tests/test_loop_guards.py` and e2e |
| Planning (`--planning`) | Works, with limits | The model writes the steps and the engine runs them one at a time, in order. A failed plan is reported as failed. `SUBTASK`, `DECISION` and `CHECKPOINT` steps are not implemented and say so. There is no replanning |
| Model routing and delegation | Not audited | Present in the code; not covered by the work in `CHANGELOG.md` |
| Subagents (task tool) | Works, with limits | Run in PLAN mode (read-only); a subagent turn that fails is reported as failed. Not audited further |

## Safety

| Area | Status | How it is checked, and the limits |
|------|--------|-----------------------------------|
| Approval prompts (`NORMAL` mode) | Works | Each write, edit, command and git change asks first. You can only judge what you can read |
| PLAN mode | Works | An allowlist built from `cortex/core/tool_policy.py`: only read-only and bookkeeping tools run, and an unclassified tool is refused. `tests/unit/core/test_tool_policy.py` fails when a tool has no class |
| Command blocklist | Works, with limits | A 98-command matrix (`tests/unit/core/test_security_command_matrix.py`). It is a filter: a script the model writes and then runs is not inspected |
| Command sandbox (`command_sandbox.mode: bubblewrap`) | Optional | Linux only, off by default; tested against real bubblewrap. Confines writes; the disk stays readable and the network open unless configured. [SECURITY.md](SECURITY.md) |
| `/rollback` (file tools) and `/undo`, `/redo` (git checkpoint) | Works, with limits | e2e tests, including a shell command that deletes a directory. `/undo` does not restore git-ignored files or move the branch back |
| AST refactoring | Works, with limits | Renames in one file with a syntax check; refuses a rename that other files mention unless `scope="file"` is given. It does not update callers in other files |

## Memory

| Area | Status | How it is checked, and the limits |
|------|--------|-----------------------------------|
| Session memory (`--memory`) | Works, with limits | Tracks failed approaches (counted, not repeated) and successful patterns for the session |
| Long-term memory (`[memory]` extra, `semantic_memory.enabled`) | Works, with limits | Stores decisions, conventions, facts and summaries of solved problems; duplicates collapse; results rank by similarity, confidence and age; `remember` and `/memory list/add/edit/delete`. Tests use a stub embedding model. **Whether it makes the agent better is unmeasured** |
| Metacognition (`--metacognition`) | Experimental | Three numbers (confidence, urgency, tone) updated by fixed rules, put in the prompt. Off by default; no evidence it helps |

## Measuring

| Area | Status | How it is checked, and the limits |
|------|--------|-----------------------------------|
| Benchmark (`python -m bench`) | Works | 20 tasks, each checked to fail as shipped and pass when solved; the whole path is tested with a scripted model. [BENCHMARK.md](BENCHMARK.md) |
| Ablation of planning, memory and metacognition | **Not run** | The runner supports it. It needs about 480 real model runs; the defaults are not yet backed by a table |
| Cognitive Gym (`/gym`) | Works, with limits | `/gym --bench <task>` succeeds only if the task's tests pass. A free-form `/gym --goal` session is reported as unchecked. There is no challenge generator |

## Components and packaging

| Area | Status | How it is checked, and the limits |
|------|--------|-----------------------------------|
| Python 3.9 to 3.12 | Works | CI matrix on Linux, Windows and macOS |
| Base install without the memory extra | Works | CI smoke job: `cortex --help`, `python -m cortex --version`, and no `chromadb` import |
| Docker image | Works | CI builds it and checks it starts, runs as non-root and has git and ripgrep |
| Rust native layer (`rust/`) | Optional | Its tests run in CI. Off by default and the speed-up is unmeasured. The Python AST parser does not use the Rust parser (it returns a summary, not the tree the Python code reads); search and tokenizing have Python fallbacks |
| Go services (`go/`) | Optional | Built and tested in CI. Cortex has no client for them and does not use them |
| Unattended runs (`cortex run`): a task on its own git worktree and branch, a verify command as the gate, retries with the failure shown, budgets, a JSON result, discard on failure | Works in tests | Tested in-process with a scripted model and real git, and as a real process over HTTP to a stand-in OpenAI-style server (the wrapper script against a fake `cortex`). Not yet run with a real model. Linux and macOS in practice; Windows untested; see [HEADLESS.md](HEADLESS.md) for what it does not protect |
| OpenAI-compatible provider (OpenAI, vLLM, llama.cpp, LM Studio) | Works in tests | Tests stand in for the SDK client: connection settings, tool calls (including untidy ones from local models), usage, streaming, errors, the configured context window. Not yet run against a live server |
| An MCP server; an HTTP API or webhooks; a research framework | Not implemented | Older documents said otherwise; those claims were removed |

## Check it yourself

```bash
pip install -e ".[dev]"
pytest tests -q                  # offline; no model or network needed
python -m bench verify           # the benchmark tasks are sound
```
