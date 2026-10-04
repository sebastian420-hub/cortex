# Safety model: what Cortex stops, and what it does not

Cortex runs a language model that can read files, edit files and run shell commands on your
machine. This page says which protections exist, what each one really prevents, and where you
are still on your own. If you only read one line: **by default, a command the model runs has
the same power as a command you type.**

## The layers

| Layer | What it does | What it does not do |
|-------|--------------|---------------------|
| **Approval prompts** (`NORMAL` mode, the default) | Each file write, edit, shell command and git change asks you first. | Nothing if you start with `--auto-approve`. You can only judge what you can read: a prompt for `python build.py` does not show you what `build.py` does. |
| **PLAN mode** (`--plan-mode`) | Allows only tools classified as read-only (reading, searching, git status/diff/log, web) or agent bookkeeping (todo list, plans). Everything else is refused, including shell commands and `run_tests`. A tool nobody classified is refused too. See `cortex/core/tool_policy.py`. | It does not stop you switching mode with `/mode`. |
| **Command blocklist** (`cortex/core/security.py`) | Refuses well-known destructive commands before they run, in every mode: `rm -rf` in any flag spelling, recursive `rm`/`chmod`/`chown` on system or home directories, `find -delete`, `curl … \| sh`, `git push --force`, `git reset --hard`, `git clean -f`, `dd of=/dev/…`, fork bombs. It looks inside `&&`, `;`, pipes, `sudo`/`env`/`xargs` and `sh -c '…'`. | It is a filter, not a boundary. It cannot see what a script does, so *write a script, then run it* gets past it. Treat it as a seatbelt, not a wall. |
| **Undo** (`/rollback`, `/undo`, `/redo`) | Recovery, not prevention. `/rollback` restores the exact bytes of every file the last request created or edited through Cortex's file tools (works without git). `/undo` restores the whole project to before the last request, shell commands included, from a git checkpoint kept on a private ref; your branch, index and stash are untouched. | `/undo` does not restore files git ignores (build output, virtual environments, logs) and does not move the branch back if a command committed or reset (it prints the command that does). Neither reverses anything that left your machine: a push, an upload, an email. |
| **Command sandbox** (`command_sandbox.mode: bubblewrap`, Linux, off by default) | Runs shell commands and tests in a namespace where the filesystem is read-only except the project directory and a private `/tmp`. | See below. |

## The command sandbox, precisely

Turn it on in `config.yaml`:

```yaml
command_sandbox:
  mode: bubblewrap     # "none" (default) or "bubblewrap"
  network: true        # false: commands cannot reach the network
  private_home: false  # true: the home directory is hidden from commands
  writable: []         # extra directories commands may write to (a pip cache, say)
```

It needs the `bwrap` program (`apt install bubblewrap`). If you ask for it and it cannot be
provided (not Linux, `bwrap` missing) the command is **refused**, never run unconfined.

With `mode: bubblewrap`:

- Commands can **write** only inside the project directory (and any `writable` paths) and a
  private, empty `/tmp`. A `rm -r ~/Documents` inside the sandbox fails with "Read-only file
  system".
- Commands can still **read** everything you can read, including `~/.ssh` and other secrets,
  unless you set `private_home: true`. (With `private_home` git and other tools will not see
  your `~/.gitconfig` either.)
- The **network is open** unless you set `network: false`. While it is open, a command can send
  any file it can read to anywhere. Setting it to false also stops `pip install`, `git push` and
  the like.
- The model's own API traffic is not a command and is not affected.
- The project directory is fully writable, including `.git`. The sandbox protects the rest of
  your machine, not your project; that is what `/undo` is for.
- Tools that live under `/tmp` (a virtual environment created there, say) are invisible inside
  the sandbox because `/tmp` is replaced.

The sandbox applies to `execute_command` and `run_tests`. Cortex's file tools for reading, writing and
editing check that paths stay inside the project directory, which is a separate, always-on rule.

## Practice sessions (`/gym`)

A practice session works in a **copy** of the project in a scratch directory. That protects your
original files and nothing else: commands still run on your machine with your permissions (or
inside the sandbox above if you enabled it), and can reach anywhere outside the copy. The model
is told this, not told it is "safe".

## Recommendations

- For everyday work, keep `NORMAL` mode and read what you approve.
- For anything unattended (`--auto-approve`, a long task, a model you do not trust, a repository
  you did not write), turn on `command_sandbox` and set `network: false` if the task does not
  need the network, or run Cortex inside a container or a disposable VM. That is the only setup
  where a mistake or a hostile instruction in a file the model reads cannot reach your
  credentials.
- Work in a git repository so `/undo` is available, and commit before you hand over a big task.
- Prompt injection is real: text in a web page, an issue or a source file can tell the model to
  do something you did not ask. The layers above limit the damage; none of them can recognise
  the instruction.
