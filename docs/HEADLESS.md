# Unattended runs: `cortex run`

`cortex run` does one task with nobody watching, and tells you truthfully how it went. It is meant
for a scheduler (cron, a systemd timer, CI): "every night, try to fix the failing tests, and leave
me a branch if you manage to".

```bash
cortex run --task "Fix the failing test in test_calc.py" \
           --verify "python -m pytest -q" \
           --json
```

> **Status.** This is tested with a scripted model, and with a real `cortex run` process talking
> over HTTP to a stand-in server that speaks the OpenAI chat API. It has **not yet been run with a
> real model**. Try it on a throwaway repository first, and treat the first runs as an experiment.

## The idea in four lines

1. The task runs on a **new branch in a separate git worktree**. Your own checkout is never touched.
2. The agent works there with every action pre-approved, because nobody is there to approve.
3. A **command you choose** (`--verify`, usually your tests) decides whether it worked. The agent's
   own account counts for nothing. If it fails, the agent is shown the failure and tries again.
4. A run that verified **keeps its branch** (one commit). A run that did not leaves **nothing
   behind** in your repository, and is still reported, with the reason.

## Quick start

With a local model on another machine, for example a vLLM server on a GPU box
(see [DEPLOYMENT.md](DEPLOYMENT.md#local-models-a-vllm-llamacpp-or-lm-studio-server)):

```bash
export OPENAI_BASE_URL=http://gpu-box:8000/v1
export CORTEX_OPENAI_CONTEXT_WINDOW=65536

cd ~/projects/myrepo                    # a git repository with at least one commit
cortex run --provider openai --model qwen3-coder \
           --task "Fix the failing tests. Fix the code, not the tests." \
           --verify "python -m pytest -q" \
           --protect "tests/*"
```

With Ollama: `cortex run --provider ollama --model qwen2.5-coder:32b ...`.

You must say how the work is checked, with `--verify COMMAND` or `--no-verify`. There is no default,
because "no check" should be a decision. A longer task can come from a file (`--task-file`).

What you get back (the text form; add `--json` for the JSON document described below):

```
PASSED: verification passed (attempt 1 of 2)
run:     20261004-152035-4b167d
branch:  cortex/fix-the-failing-test-in-test-70bbe6 (1 file(s) changed)
review:  git diff d9ab40f0d56f..cortex/fix-the-failing-test-in-test-70bbe6
spent:   3 model calls, 2 tool calls, 450 tokens, 0.85s
checked: python -m pytest -q
```

Review the branch the way you would anyone's: `git diff <base>..<branch>`, run your CI on it, then
merge it or `git branch -D` it.

## What happens in a run

```
 your repo ──► new branch + separate worktree, from the committed base
                    │
                    ▼
        agent works (pre-approved, budgets on)  ◄──────────────┐
                    │                                           │ failure output shown,
                    ▼                                           │ if attempts and budget remain
          verify command runs in the worktree ── fails ─────────┘
                    │ passes
                    ▼
     protected paths untouched? something actually changed?
                    │
        ┌───────────┴────────────┐
      yes                         no
        ▼                          ▼
  one commit, branch kept     worktree and branch removed
  status: passed              status says why (failed, no_changes, ...)
```

Details that matter:

- **The base.** The branch starts from the *committed* state of `--base` (default `HEAD`).
  Uncommitted changes in your checkout are not part of it. Your checkout, its branch, its index and
  its files are not touched, so you can keep working while a run is going.
- **The prompt.** The agent gets your task, a note that it is unattended (nobody can answer
  questions, so it should state its assumptions), and the verify command it will be checked with.
  After a failed verification it gets the command and the last 4,000 characters of its output.
- **Where it works.** In a temporary directory named after your project, which is removed at the
  end. The worktree is made from your repository, so anything in your repository's `.git` (branches,
  tags, config) is shared with it. See "Safety" below.
- **The commit.** One commit on the new branch, with the task and the verify command in its
  message, authored by you if git knows who you are and by `Cortex <cortex@localhost>` if not
  (a fresh scheduler account has no identity). Your repository's commit hooks are not run: the
  verify command is the gate. Files that running tests leaves behind (`__pycache__`, `*.pyc`,
  `.pytest_cache`, `.mypy_cache`) and Cortex's own `.cortex/` directory are never committed.
- **Imports.** The worktree (and its `src/` directory, if there is one) is put first on
  `PYTHONPATH` for the whole run. Without this, a project installed in editable mode would have
  its tests import the code from your own checkout, the code from *before* the task. That was
  measured: a correct fix failed its tests, and a regression the agent introduced passed them. The
  variable is restored afterwards.
- **Settings.** Your usual configuration file applies (`--config`, else `config/default.yaml`),
  with these changes: all actions are pre-approved, there is nobody to ask whether to continue
  past the iteration limit, and undo checkpoints are off (the worktree is the undo: it is thrown
  away on failure). An explicit `--config` that does not exist is an error, never silently the
  defaults.
- **Tools.** The agent has its usual tools except those that cannot work or should not be used
  unattended: `ask_user_question` (nobody to answer), and `git_push`, `git_pull`, `git_fetch`,
  `git_branch` and `git_checkout` (they reach outside the worktree). Whatever your configuration
  lists under `tools.disabled` stays disabled too.

## Choosing the verify command

The command runs in the worktree, through a shell, with no terminal, and must exit 0. It is
stopped, with everything it started, after `--verify-timeout` seconds (default 600).

| Project | Typical command |
|---------|-----------------|
| Python | `python -m pytest -q` (use `python -m`: see "Imports" above) |
| Python, a virtualenv outside the worktree | `/path/to/venv/bin/python -m pytest -q` |
| Node | `npm test --silent` |
| Go | `go test ./...` |
| Rust | `cargo test --quiet` |
| Anything | `make check`, or a script that runs the tests, the linter and the type checker |

Three things to know:

- **A virtualenv inside the repository is not in the worktree**, because it is not committed. Use
  an absolute path to its interpreter, or a command that finds it.
- **The agent can edit the tests.** A command that only runs the project's own tests can be
  satisfied by weakening them. Say so in the task, and use `--protect` for the paths that must not
  change, for example `--protect "tests/*"`. A run that changes a protected path **fails even if
  the verify command passes**. Also run your CI on the branch before you merge it.
- **`--no-verify`** is for tasks with no mechanical check (documentation, say). The result is then
  `unverified`, never `passed`, and the scheduler wrapper never pushes it.

The verify command runs code the agent wrote (new tests, a changed `conftest.py`), so when you
configure `command_sandbox` it goes through the sandbox too, and is not run at all if the sandbox
was asked for and cannot be provided.

## The result

The text summary is for people. For machines, use `--json` (one JSON document on stdout) or
`--output FILE` (the same document, in a file). Nothing else is ever written to stdout: the agent's
running commentary goes to stderr, or nowhere with `--quiet`.

### Status and exit code

| `status` | Meaning | Exit | Branch kept |
|----------|---------|:----:|:-----------:|
| `passed` | the verify command passed | 0 | yes |
| `unverified` | no verify command (`--no-verify`); nothing checked the work | 0 | yes |
| `failed` | verification kept failing, or a protected path was changed | 1 | no (`--keep-failed`) |
| `no_changes` | the agent finished but changed no file | 1 | no |
| `agent_failed` | the agent stopped with an error, for example the model server was unreachable | 1 | no (`--keep-failed`) |
| `budget_exceeded` | a step, token or time budget ran out | 1 | no (`--keep-failed`) |
| `interrupted` | a termination signal or Ctrl-C arrived | 1 | no (`--keep-failed`) |
| `crashed` | an unexpected error in Cortex itself | 1 | no (`--keep-failed`) |
| `setup_error` | could not start: not a git repository, bad arguments, an unreadable task file or config, a model provider that is not set up, a required sandbox that is unavailable | 2 | no |

Exit code 0 means "completed as asked", and `unverified` is part of that only because you asked
for no check. A scheduler that must not accept unverified work should read `status`.

### The JSON document

A real result (from a run against a stand-in model server, trimmed):

```json
{
  "schema": 1,
  "run_id": "20261004-152035-4b167d",
  "status": "passed",
  "reason": "verification passed (attempt 1 of 2)",
  "task": "Fix the failing test in test_calc.py",
  "repo": "/home/me/projects/calc",
  "base": "d9ab40f0d56f2b02810a2452516face58bf30485",
  "branch": "cortex/fix-the-failing-test-in-test-70bbe6",
  "head": "de063363953156479686a366aabe358f13aa1cc9",
  "files_changed": ["calc.py"],
  "diff_stat": "calc.py | 2 +-\n 1 file changed, 1 insertion(+), 1 deletion(-)",
  "new_branches": [],
  "verify_command": "python -m pytest -q",
  "attempts": [
    {
      "turn": "ok",
      "turn_error": null,
      "verification": {
        "passed": true, "exit_code": 0, "timed_out": false,
        "seconds": 0.39, "output_tail": ".    [100%]\n"
      }
    }
  ],
  "usage": {
    "steps": 3, "tool_calls": 2,
    "input_tokens": 360, "output_tokens": 90,
    "estimated": false, "cost_usd": null
  },
  "budget": {"max_steps": 40, "max_tokens": 1000000, "timeout_s": 3600, "exceeded": null},
  "model": "qwen3-coder", "provider": "openai", "sandbox": "none", "seconds": 0.85
}
```

| Field | Meaning |
|-------|---------|
| `status`, `reason` | what happened, and why, in a sentence |
| `base`, `branch`, `head` | the commit it started from; the branch and its commit. `branch` and `head` are `null` unless the branch was kept |
| `files_changed`, `diff_stat` | what the agent changed. Filled in even when the work was discarded, so a failed run still shows what it tried |
| `new_branches` | branches that appeared in the repository during the run, other than its own. They are **not deleted** (one may be yours); see "Safety" |
| `attempts` | one entry per attempt: how the agent's turn ended and what the verify command said (`output_tail` is the last 4,000 characters) |
| `usage` | `steps` are model calls. Tokens are what the server reported; if any call reported none they are estimated and `estimated` is true. `cost_usd` is `null` unless you gave `--price-in` and `--price-out` (dollars per million tokens): a cost is never guessed |
| `budget` | the limits, and which one (`steps`, `tokens`, `time`) cut the run, if one did |
| `sandbox` | the `command_sandbox` mode in force: `none` or `bubblewrap` |

`schema` is 1. Fields may be added; existing ones will not change meaning without a new schema
number.

## Budgets

An unattended run is bounded, because nobody is watching it. All are over the whole run, retries
included. `0` means no limit.

| Flag | Default | Counts |
|------|--------:|--------|
| `--max-steps` | 40 | model calls |
| `--max-tokens` | 1,000,000 | input plus output tokens |
| `--timeout` | 3600 | wall-clock seconds |
| `--retries` | 1 | extra attempts after a failed verification |
| `--verify-timeout` | 600 | seconds one run of the verify command may take |

A budget stops the run by asking the agent to shut down at its next step, so the worktree is still
cleaned up and the result is still written. A run is only cut when the agent still wanted to
continue: a final answer that happens to cross a limit is a finished run. Model calls made for
context summarization (the `llm` and `hybrid` strategies) are counted too.

Limits you should know about:

- Budgets are checked **between** model calls. A single call that hangs, or a single long command
  the agent starts, is not interrupted by them (tools have their own time limits). That is why the
  scheduler wrapper puts a hard wall-clock limit around the whole process.
- The time limit includes verification, but the verify command is only bounded by
  `--verify-timeout`, so a run can overshoot `--timeout` by about that long.

## Safety

What it protects:

- Your checkout (files, branch, index) is not touched while a run is going.
- A run that does not verify leaves no branch of its own, no worktree and no files in your
  repository. (The one exception, a branch the agent made some other way, is `new_branches`.)
- A run cannot publish: the agent has no `git push`, `pull` or `fetch` tool, and the wrapper script
  pushes only a branch that verified.
- A termination signal or Ctrl-C stops the run cleanly, with the worktree removed and a result
  written. A second signal does what it normally would.

What it does **not** protect, and you must decide about:

- **Pre-approved actions are the point, and they are real.** The agent runs shell commands, writes
  files and (unless you restrict it) uses the network with *your* permissions. The worktree isolates
  files in your repository, not your machine. A command can still read your home directory,
  write outside the repository or reach the network. The command blocklist catches well-known
  destructive forms but is a filter, not a boundary.
- **For a real boundary**, turn on `command_sandbox` (`mode: bubblewrap`, Linux; see
  [SECURITY.md](SECURITY.md)) and add `--require-sandbox`, which refuses to run unless commands are
  confined. Consider `network: false` and `private_home: true` as well, or run Cortex in a container
  or a VM, and give that account no credentials that can publish anything.
- **What the sandbox confines:** `execute_command`, `run_tests` and the verify command. The agent's
  git tools run in Cortex's own process and are not confined (which is one reason the dangerous
  ones are removed). Inside the sandbox, `git status` works but `git add` and `git commit` fail
  with "Read-only file system", because the worktree's git data lives in your repository, outside
  the writable directory. That is protective, and harmless: Cortex makes the commit itself.
- **A shell command can still use git.** The agent has no branch tools, but `git checkout -b` through
  the shell works unless the sandbox is on. If it leaves the task branch, whatever was verified
  (commits and uncommitted changes alike) is moved onto the task branch. Branches created along the
  way are listed in `new_branches` and left alone, because deleting a branch that might be yours is
  worse than leaving a stray one.
- **Hooks** from your configuration run in an unattended run like any other.
- A model can write a test that passes trivially. See "Choosing the verify command".

## Running it on a schedule

Anything that can run a command can schedule it; the interface is an exit code and a JSON file.
[`examples/scheduled/`](../examples/scheduled) has what you need for cron and systemd:

| File | What it is |
|------|------------|
| `run-task.sh` | a wrapper that adds a lock (runs never overlap), a hard wall-clock limit, the result kept per run, an opt-in push of a branch that **verified**, and clean-up of old results |
| `crontab.example` | a nightly run from cron |
| `cortex-nightly.service`, `cortex-nightly.timer` | a systemd user service and timer (`Persistent=true` catches up a missed night) |
| `nightly.env.example` | the settings the service reads |
| `tasks/fix-failing-tests.md` | a sample task file |

Using the wrapper:

```bash
export CORTEX_REPO=~/projects/myrepo
export CORTEX_TASK_FILE=~/.config/cortex/tasks/fix-failing-tests.md
export CORTEX_VERIFY="$HOME/projects/myrepo/.venv/bin/python -m pytest -q"
export OPENAI_BASE_URL=http://localhost:8000/v1 CORTEX_OPENAI_CONTEXT_WINDOW=65536

examples/scheduled/run-task.sh --provider openai --model qwen3-coder --protect 'tests/*'
```

It keeps `~/.cortex/runs/<time>.json` (the result), `.summary` and `.log` (the agent's commentary),
prints a one-line outcome, and exits with Cortex's code, or 124 if its wall-clock limit stopped
the run, or 3 if a requested push failed. Set `CORTEX_PUSH=1` to push the branch of a run that
`passed` (never `unverified`, failed or interrupted ones) to `origin`.

A good pattern is to **let it push, and let your CI judge**: the scheduled job pushes `cortex/...`
branches, your CI runs on them, and you merge the ones you like in the morning.

Tips:

- Take the lock seriously: a model server on one GPU should not serve two runs at once. The wrapper
  uses `flock` (not installed by default on macOS); without it, runs can overlap.
- Several tasks means several schedule entries (or several calls in one script). Each is its own
  run, branch and result.
- Pick a time the machine is otherwise idle, and set `CORTEX_WALL_TIMEOUT` to what you are willing
  to spend.

## With a local model

- **Tell Cortex the context window** (`CORTEX_OPENAI_CONTEXT_WINDOW`, or `CORTEX_OLLAMA_NUM_CTX`
  for Ollama). Cortex sends about 7,000 tokens of tool definitions before your first word; a
  smaller window than the server was started with makes it forget its instructions. See
  [DEPLOYMENT.md](DEPLOYMENT.md).
- **Tool calling has to be on in the server**, or the model can talk but not act.
- **Measure before you trust.** Run `python -m bench` against your model first
  ([BENCHMARK.md](BENCHMARK.md)): it tells you how often *that* model fixes *those* kinds of
  tasks, which is what decides whether a nightly run is worth leaving unattended.
- **Retries help weaker models.** Seeing the failing output is often enough for a second attempt to
  succeed. `--retries 2` costs only time when the model is local.
- Keep the first tasks small and mechanical (fix a failing test, add a type annotation, update a
  deprecated call) and widen as the results earn it.

## What it does not do

- It does not open pull requests, send notifications or merge anything. The wrapper can push a
  branch; the rest is your CI and your hands.
- One task per invocation. There is no queue; schedule several runs instead.
- It has not been run with a real model yet (see the note at the top), and it is Linux and macOS
  only in practice: the sandbox is Linux-only, the wrapper script is bash, and Windows is untested.
- Repositories with submodules or large-file storage are untested.
- Budgets do not interrupt a model call or a command that is already running (see "Budgets").

## Troubleshooting

| You see | Why, and what to do |
|---------|---------------------|
| `setup_error`: "is not inside a git repository" | Run it in, or point `--project-dir` at, a git repository with at least one commit |
| `setup_error`: "the model provider is not set up" | The message above it (on stderr) says what to set: a key, `OPENAI_BASE_URL`, or that Ollama is not running |
| `setup_error`: "A sandbox was required" | Set `command_sandbox.mode: bubblewrap` in the config, or drop `--require-sandbox` |
| `setup_error`: "The configuration file ... does not exist" | The `--config` path is wrong. This is an error on purpose: the defaults would have run without the settings you meant |
| `no_changes` | The agent finished without editing anything. Often the task was a question, or the model did not call its tools: check the server has tool calling on |
| `failed`, with the verify output showing the *old* behaviour | Your tests are importing code from somewhere other than the worktree. Use `python -m pytest`, or check how the project is installed |
| `agent_failed` | Read `attempts[].turn_error`: usually the model server was unreachable or rejected the request |
| `budget_exceeded` | Raise the limit, or make the task smaller. A model that spends 40 steps without finishing is often lost |
| Leftover `cortex-run-*` directories in `/tmp`, or `cortex/*` branches | A run that was killed with SIGKILL could not clean up. `git worktree prune`, `rm -rf /tmp/cortex-run-*`, `git branch -D <name>` |
