# Measuring the agent

Whether a feature helps is a question for numbers, not for documentation. `bench/` is the
instrument: 20 small tasks whose outcome is decided by running tests, a runner that records what
the agent did, and reports.

```bash
python -m bench list                       # the tasks
python -m bench verify                     # check the tasks themselves (no model needed)
python -m bench run --model <name> --provider <provider> --runs 3
python -m bench report bench/reports/<file>.json
```

## The tasks

Fifteen **bug fixes** and five **refactors**. Each is a tiny Python project defined as data in
`bench/suite.py` (so the repository's own test run never collects them): the starting files, a
reference solution, and the test files that decide the outcome.

- A bug fix has one planted bug and tests that describe the correct behaviour. Four are traced
  through a second module, so the failing test is not in the file with the bug.
- A refactor must keep behaviour and change structure: rename a function across files, extract a
  duplicated check into one function, replace magic numbers with named constants, move a function
  to a new module, turn a hand-written class into a dataclass. The tests check the behaviour and
  look at the code's structure with `ast`.

Prompts describe symptoms the way a user would; a test makes sure they do not contain the fix.

## How a task is judged

The **verifier** decides, never the agent's account of its own work:

- The task's test files are written back before they run, so editing or deleting a test cannot
  help.
- If the agent added a `conftest.py`, `pytest.py`, `sitecustomize.py` or a config file that could
  change how the tests run, the verifier refuses to run and the task fails.
- A timeout fails the task.

`python -m bench verify` checks the tasks themselves: each must **fail as shipped** (on the bug,
not on an import error) and **pass with its reference solution**. CI runs it.

## What a run records

Per task and run: pass or fail (from the verifier), **steps** (model calls), tool calls,
**tokens** (the provider's reported usage; flagged as an estimate if any call reported none),
**cost** (only when you pass `--price-in` and `--price-out`, in USD per million tokens; otherwise
it says n/a and is never guessed) and time. A run that crashes is recorded, not lost.

Reports are written as JSON and a markdown table: pass rate overall and per kind, mean steps and
tokens, cost.

## Comparing settings (ablation)

`--planning`, `--memory` and `--metacognition` switch the agent's optional features on;
`--ablate planning,memory,metacognition` runs every on/off combination, and `--runs N` repeats
each setting. A model's answers vary from run to run, so use several runs before believing a
difference.

```bash
python -m bench run --model <name> --provider <provider> \
    --ablate planning,memory,metacognition --runs 3 --max-iterations 30 \
    --price-in 3 --price-out 15 --label ablation
```

That is 8 settings x 3 runs x 20 tasks = 480 agent runs, so it takes real time and money.
**This has not been run**: the defaults (`--planning`, `--memory` and `--metacognition` off)
are the conservative choice, not the result of an experiment. When it has been run, the report
belongs in `bench/reports/`, and the defaults should follow from it.

## Practising on a task

`/gym --bench <task_id>` (`/gym --bench list` shows the ids) lets the agent work on a benchmark
task in a scratch copy of the project and reports whether the task's tests pass.

## Limits

Twenty small Python tasks measure a narrow slice of what a coding agent does: they say little
about large codebases, other languages, long tasks or ambiguous requests. Treat the numbers as a
way to compare two versions of Cortex against each other, not as a score.
