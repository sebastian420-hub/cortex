# Running Cortex

Cortex is a command-line program that runs on your own machine and talks to a language model. It
is a client: it listens on no port and needs no server. This page covers installing it, choosing
a model, running it unattended and in a container, and where it keeps its state. For what its
safety features do and do not stop, read [SECURITY.md](SECURITY.md).

## Requirements

- Python 3.9 or newer
- `git` on the path (the git tools and `/undo` use it)
- An API key for a cloud model, or [Ollama](https://ollama.ai/) for a local one

## Install

From a clone of the repository:

```bash
pip install .                # the base install
pip install ".[memory]"      # adds long-term (vector) memory; pulls in PyTorch, so it is optional
pip install ".[hybrid]"      # build tooling for the optional Rust and Go components
```

Check it works:

```bash
cortex --version
cortex --help
```

## Choose a model

| Provider | Set | Run |
|----------|-----|-----|
| OpenRouter (the default) | `OPENROUTER_API_KEY` | `cortex` |
| Anthropic | `ANTHROPIC_API_KEY` | `cortex --provider anthropic --model <model>` |
| DeepSeek | `DEEPSEEK_API_KEY` | `cortex --provider deepseek --model <model>` |
| Ollama (local, no key) | none | `cortex --provider ollama --model llama3.2` |

Cortex has no OpenAI provider. For a fully offline machine use Ollama and set `CORTEX_OFFLINE=1`
so it never tries to download tokenizer data.

### Local models: the context window

Before your first word Cortex sends roughly 7,000 tokens: the definitions of its tools (about
6,000 with every tool, fewer without `--planning`) and its system prompt. A server that gives the
model a smaller window than that silently drops the start of the conversation, system prompt
first, and the model then behaves as if it had never been told what it is.

So with Ollama, Cortex always asks for a window explicitly: 32,768 tokens by default, or
whatever `ollama.num_ctx` in the config file or the `CORTEX_OLLAMA_NUM_CTX` environment variable
says (the environment wins). It also sizes its conversation history to that window minus the tool
definitions, and warns if the window leaves too little room (below about 14,000 tokens). A larger
window costs memory on the machine running the model; raise it for long tasks if you have the
room.

## Configure

Settings come from, in increasing priority: built-in defaults, a YAML file given with
`--config`, `CORTEX_*` environment variables, and command-line flags. `config/default.yaml` is an
example to copy.

Useful environment variables: `CORTEX_MODEL`, `CORTEX_PROVIDER`, `CORTEX_MODE`,
`CORTEX_MAX_ITERATIONS`, `CORTEX_MAX_TOKENS`, `CORTEX_OUTPUT_FORMAT`, `CORTEX_OFFLINE`.

Features that are off unless you ask for them:

| Flag | What it turns on |
|------|------------------|
| `--planning` | the planning tools (`create_and_execute_plan` and friends) |
| `--memory` | layered session memory (long-term memory also needs the `memory` extra and `semantic_memory.enabled: true`) |
| `--metacognition` | the experimental confidence/urgency/tone block in the prompt |

## Run it unattended

```bash
cortex -p "fix the failing test in tests/test_parser.py"      # one prompt, then exit
```

In one-shot mode the exit code is 0 only if the model finished its turn; it is 1 if the turn
failed, hit the iteration limit, or was stopped by the loop guard. It does **not** say whether the
work is correct: run your tests afterwards.

Before running unattended, read the "Recommendations" in [SECURITY.md](SECURITY.md). In short:
work in a git repository so `/undo` is available, turn on `command_sandbox` (and set
`network: false` if the task allows it), and prefer a container or disposable VM for anything you
do not trust.

## Run in a container

```bash
docker build -t cortex .
docker run --rm -it -v "$PWD":/work -e OPENROUTER_API_KEY cortex
```

The image runs as an ordinary user with your project mounted at `/work`. A container limits what
the agent can reach on your disk to what you mounted; it does not limit the network.

## What Cortex stores

| Where | What | When it goes away |
|-------|------|-------------------|
| `~/.cortex/sessions/` | saved conversations | pruned by the `session_retention` settings |
| `~/.cortex/backups/` | file backups for `/rollback` | after the next request, or when the session ends |
| `refs/cortex/*` in your git repository | checkpoints for `/undo` | when the session ends; stale ones after 7 days |
| `.cortex/semantic_db/` in the directory you start in | long-term memory (only if enabled) | `/memory clear`, or delete the folder |

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
