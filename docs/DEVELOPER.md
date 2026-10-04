# Cortex Developer Guide

For contributors and anyone who wants to understand the internals. Start with
[CONTRIBUTING.md](../CONTRIBUTING.md) for setup and how changes are made; the design is in
[CORTEX_TECHNICAL_SPEC.md](CORTEX_TECHNICAL_SPEC.md) and the safety model in [SECURITY.md](SECURITY.md).

## The shape of the code

```
cortex/
├── agent.py                  # the agent loop (one user request = one turn)
├── cli.py, cli_commands/     # command line, REPL commands (/undo, /memory, /gym, ...)
├── core/
│   ├── turn.py               # TurnResult: how a turn ended
│   ├── agent_permissions.py  # approval prompts, PLAN mode
│   ├── tool_policy.py        # every tool's class (read-only, bookkeeping, mutating, runs code)
│   ├── security.py           # path checks and the command blocklist
│   ├── command_sandbox.py    # optional bubblewrap confinement
│   ├── transaction.py        # per-request file backups (/rollback)
│   ├── checkpoints.py        # git snapshots (/undo, /redo)
│   ├── planning.py           # the planning engine (--planning)
│   ├── memory/               # long-term memory: contract, ranking, vector store
│   ├── memory_layers/        # working, session and state memory
│   ├── prompts/              # PromptBuilder
│   ├── providers/            # OpenRouter, Anthropic, DeepSeek, Ollama, OpenAI-compatible; token usage
│   └── gym/                  # practice sessions
├── headless/                 # cortex run: worktree per task, verify gate, budgets, JSON result
├── tools/                    # the tools the model can call
├── utils/message_validation.py   # keeps tool-call messages valid for chat APIs
├── native/, cache/           # optional Rust bindings and file cache
bench/                        # the benchmark (python -m bench)
examples/scheduled/           # cron and systemd files for unattended runs
tests/                        # the offline test suite; tests/e2e drives the real loop
```

## One turn, in order

1. A transaction opens, and a git checkpoint is marked as due.
2. The system prompt is rebuilt (fixed part first, changing part last); long-term memory is looked
   up once for this request.
3. The model is called with validated messages. Its tool calls are checked by the permission
   layer, the first one that could change anything triggers the checkpoint, and each runs through
   a tool created with the session's transaction manager.
4. Results go back in strict order after their requests. The loop guard watches for repeats.
5. The turn ends with a `TurnResult`. The transaction stays open so `/rollback` works.

## Adding a tool

1. Write the tool class in `cortex/tools/` and register it (schema and class) in
   `cortex/tools/registry.py`.
2. Add it to `cortex/core/tool_policy.py` with the right class. Do not skip this: PLAN mode
   refuses a tool that has none, and a test fails.
3. If it writes files, call `self.backup_file(path, operation)` before writing so `/rollback` can
   restore them.
4. If it runs commands or tests, go through `core/command_sandbox.confine` so the sandbox applies.
5. Add a test. A tool that can change things needs a test for the case that must be refused.

## Testing

```bash
pytest tests -q               # offline: no model, no network, a throwaway git identity
python -m bench verify        # the benchmark tasks are sound
```

`tests/e2e/scripted.py` is a fake provider that replays a fixed list of model messages. Use it to
test agent behaviour end to end. Open bugs live in `KNOWN_BUGS` in `tests/e2e/conftest.py` as
strict expected failures, so fixing one forces its entry to be deleted.

## Code style

- Black, line length 100 (the version is pinned); flake8; the files listed under
  `[tool.mypy] files` in `pyproject.toml` must type-check.
- Use `validate_path` from `cortex.core.security` for any path that comes from the model.
- Say only what is true in comments, docs and messages: if a feature is off by default, partial or
  unmeasured, the text says so.
