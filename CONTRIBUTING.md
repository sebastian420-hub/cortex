# Contributing to Cortex

Thanks for helping. This page is the short version of how to work on the code.

## Set up

```bash
git clone https://github.com/sebastian420-hub/cortex.git
cd cortex
python -m venv .venv && source .venv/bin/activate     # Python 3.9 or newer
pip install -e ".[dev]"
```

Long-term (vector) memory is an optional extra because it pulls in PyTorch:
`pip install -e ".[memory]"`. Most tests do not need it. The Rust and Go layers are optional
too; see the `rust` and `go` jobs in `.github/workflows/ci.yml` for how they are built and tested.

## Run the checks

```bash
pytest tests -q                       # the whole suite; it is offline and hermetic
python -m bench verify                # the benchmark tasks themselves (no model needed)
black --check cortex tests bench      # formatting (line length 100)
flake8 cortex tests --max-line-length=120
mypy cortex/core/turn.py              # see the "Type checks" job in ci.yml for the full list
```

The tests never call a real model. `tests/e2e/` drives the real agent loop with a scripted fake
provider (`tests/e2e/scripted.py`), which is how behaviour such as "a failed plan is reported as
failed" or "/undo restores what a shell command deleted" is tested without a network.

## How changes are made here

- **Write the failing test first.** A bug report becomes a test that fails, then the fix. If you
  cannot fix it yet, add the test to `KNOWN_BUGS` in `tests/e2e/conftest.py`: it runs as a strict
  expected failure, so the suite stays green and the entry has to be deleted the moment the fix
  lands. That list is the open-bug list.
- **Keep commits small and logical**, with a message that says what was wrong and why the change
  fixes it, not only what changed.
- **Say only what is true.** A claim in the README or docs is either true (and a test proves it)
  or labelled *planned* or *experimental*. Do not describe a feature that does not exist yet.
- **Safety-relevant code gets the most care.** Changes to permissions, the command blocklist,
  transactions, checkpoints or the sandbox need tests for the case that must be refused as well as
  the case that must work. Read [docs/SECURITY.md](docs/SECURITY.md) first.
- **Measure before claiming an improvement.** `python -m bench run` records pass/fail from the
  tasks' own tests. A change that is supposed to make the agent better should say what it did to
  that number.

## Where things are

| Area | Where |
|------|-------|
| The agent loop | `cortex/agent.py` |
| Tools | `cortex/tools/` (every tool needs a class in `cortex/core/tool_policy.py`) |
| Permissions, blocklist, sandbox | `cortex/core/agent_permissions.py`, `security.py`, `command_sandbox.py` |
| Undo | `cortex/core/transaction.py` (file tools), `checkpoints.py` (git) |
| Memory | `cortex/core/memory/`, `cortex/core/memory_layers/` |
| Benchmark | `bench/` |

## Releasing

See the checklist at the top of [CHANGELOG.md](CHANGELOG.md).
