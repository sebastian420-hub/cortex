# Changelog

All notable changes to Cortex will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Release checklist

The version in `pyproject.toml`, the newest section below and the git tag must be the same number
(a test, `tests/unit/test_release_and_docs.py`, checks the first two).

1. CI is green on `main`: tests, lint, the blocking type check, `python -m bench verify`, the
   Docker job.
2. Set `version` in `pyproject.toml`.
3. Rename `[Unreleased]` below to `[X.Y.Z] - YYYY-MM-DD` (today's date) and add a fresh empty
   `[Unreleased]` above it. Keep sections newest first.
4. Commit as `release: vX.Y.Z`, then tag it: `git tag -a vX.Y.Z -m "Cortex X.Y.Z"` and
   `git push origin vX.Y.Z`.
5. Build and check: `python -m build` then `twine check dist/*`.
6. Publish, if publishing: `twine upload dist/*`. Then smoke-test it in a clean environment:
   `pip install cortex==X.Y.Z && cortex --version`.

No release has been tagged yet, so there are no tags to compare against.

## [Unreleased]

A stabilisation pass: what the documentation claimed and what the code did had drifted apart, so
each claim was either made true, with a test, or removed. Nothing here has a version number yet.

### Added
- **`/undo` and `/redo`**: restore the whole project to before the last request, including what a
  shell command did, from a git snapshot kept on a private ref (your branch, index and stash are
  untouched). `/rollback` now restores the exact bytes of the files a request changed.
- **Command sandbox** (`command_sandbox.mode: bubblewrap`, Linux, off by default): runs commands
  and tests with the filesystem read-only except the project and a private `/tmp`; network and
  home directory can be cut off. Refuses to run, rather than run unconfined, if it cannot be
  provided. [docs/SECURITY.md](docs/SECURITY.md) says what it does and does not stop.
- **`remember` tool and `/memory list|add|edit|delete`**: the model can keep a convention for
  later sessions, and you can see and manage what is stored.
- **Benchmark** (`python -m bench`): 20 verifiable tasks (15 bug fixes, 5 refactors) judged by
  their own tests, with steps, tokens and cost recorded per run and an ablation mode.
  `/gym --bench <task>` practises on one.
- `--planning`, `--memory` and `--metacognition` flags; `python -m cortex`; a `[memory]` install
  extra; `CORTEX_OFFLINE=1`.
- Turn results (`ok`, `error`, `max_iterations`, `loop_guard`, `blocked`, `interrupted`): one-shot
  mode (`cortex -p`) exits non-zero unless the turn finished.
- Providers report token usage in one shape.
- **OpenAI-compatible provider** (`--provider openai`): OpenAI, or a local vLLM, llama.cpp,
  LM Studio or SGLang server through `OPENAI_BASE_URL` (no key needed locally). The server's
  context window is set with `openai.context_window` or `CORTEX_OPENAI_CONTEXT_WINDOW` so the
  history is sized to fit. Tested with a stand-in for the SDK client, not yet against a live
  server.
- A tool-policy table classifying every tool; a test fails when a tool has no class.
- CONTRIBUTING.md; docs/SECURITY.md, docs/BENCHMARK.md.

### Changed
- Planning, layered memory and metacognition are **off unless enabled** (`--enhanced` is a
  deprecated alias for `--planning --memory`). Mood follows consecutive failures, not the lifetime
  total.
- **PLAN mode is an allowlist** of read-only tools: it now also blocks `run_tests` (it used to run
  project code) and any tool not yet classified.
- **Long-term memory has a contract**: it keeps decisions, conventions, facts and summaries of
  solved problems, not requests, raw errors or file-operation noise. Duplicates collapse; results
  rank by similarity, confidence and age; weakly related memories are not put in the prompt.
- The system prompt puts everything fixed for the session first, so provider prompt caches work,
  and long-term memory is looked up once per request instead of once per loop iteration.
- A failed plan is reported as failed; unimplemented plan steps say so instead of passing.
- A practice session in the gym succeeds only if a verifier passes; without one it is reported as
  unchecked.
- `ast_refactor` refuses a rename that other files mention unless `scope="file"` is passed.
- The Docker image is a single stage, pinned by digest, non-root, and smoke-tested in CI.
- CI: coverage counts the whole package (about two thirds, where the old gate hid its omissions),
  type checking blocks on a list of clean modules, flake8 no longer ignores undefined names or unused
  variables, black is pinned, and test counts are generated.
- Documentation rewritten so every claim is true or labelled; Python 3.9 or newer (older docs said 3.8).

### Fixed
- Local models served by Ollama were never told their context window, so Ollama's small default
  silently dropped the start of the conversation, system prompt first, since Cortex sends about
  7,000 tokens before the user's first word. Cortex now requests 32,768 tokens (configurable with
  `ollama.num_ctx` or `CORTEX_OLLAMA_NUM_CTX`), sizes its history to the window minus the tool
  definitions, and warns when the window is too small.
- The startup provider check and the model-switch message ignored `--provider` and guessed from the
  model name: with `--provider ollama` and a name such as `qwen/qwen3-coder` the check that Ollama
  is running was skipped, because the name looked like an OpenRouter model.
- Tool-call and result messages are kept in the order chat APIs require, through truncation and
  summarisation (a strict provider rejected the old order).
- The loop guard is fed by the agent loop, so it can stop a runaway turn.
- The transaction manager is connected to the file tools. Before, nothing was ever backed up and
  `/rollback` restored nothing; backups hold exact bytes (CRLF and non-UTF-8 files included).
- The command blocklist missed `rm -fr`, `find -delete`, `curl | sh`, `git push --force`,
  `git reset --hard`, `git clean -fdx`, recursive `chmod` on system paths and more.
- Rust and Go components build and test in CI (`cargo test` links; the PyO3 extension is opt-in).
- A fresh `pip install` works (packaging metadata, bundled skills, optional memory stack);
  `--config` no longer crashes and every config key is applied; the tokenizer no longer retries a
  download on every call when offline; session files are written atomically.
- With the Rust AST flag on, the Python parser returned a summary object instead of a syntax tree.
- State and memory summaries joined sections with the characters backslash-n instead of newlines.

### Removed
- Claims of an OpenAI provider, an MCP server, an API gateway, webhooks and a research framework
  (none existed), and a deployment guide written for a server.
- A broken submodule link, scratch scripts and one developer's local settings from the repository.

## [1.2.0] - 2026-02-25

### Added
- **Bio-inspired Metacognitive Core**: New internal state tracking for confidence, urgency, and emotional tone.
- **Cognitive Gym**: Autonomous practice environment for agents to improve skills in sandboxed projects.
- **Metacognitive Reflection**: Capability for agents to generate 'Synthetic Experiences' and learn from past successes/failures.
- **Dynamic System Prompting**: Metacognitive state is now injected into the system prompt for better self-awareness.

### Fixed
- Fixed critical bug where the agent and state manager used inconsistent memory bank instances.
- Fixed system prompt refresh issue where internal state wasn't being sent to the LLM.
- Adjusted appraisal logic for more realistic emotional transitions (frustration, caution).
- Improved memory bank synchronization between session and global state.

## [1.1.0] - 2026-02-24

Never published as its own release: `pyproject.toml` went from 1.0.0 to 1.2.0, and no tag was
made. The work the documentation called 1.1.0 (21 to 24 February 2026) shipped in 1.2.0.

### Added
- Session-scoped long-term (semantic) memory with global search.
- AST-driven refactoring (`ast_refactor`: rename a symbol, replace a block, with a syntax check).
- Current Claude model names.

## Rename from LocalAgent (listed as 2.0.0; not a released version)

The date was a placeholder (`2025-01-XX`) and `pyproject.toml` never carried this number; this
repository's history starts on 2026-01-20, so the date cannot be verified.

### Changed
- **BREAKING**: Renamed project from LocalAgent to Cortex
- Renamed package directory: `localagent/` → `cortex/`
- Renamed main class: `LocalAgent` → `Cortex`
- Renamed CLI command: `localagent` → `cortex`
- Updated storage directory: `.localagent/` → `.cortex/`
- Updated all documentation and references
- Updated project description to reflect unified agent capabilities (coding, cybersecurity, personal assistance)

### Migration Notes
- Users will need to reinstall: `pip install -e .`
- Old CLI command `localagent` no longer works - use `cortex` instead
- Storage directory migration: `.localagent/` → `.cortex/` (may need manual migration for existing users)
- All imports in external code will need updating: `from localagent` → `from cortex`

## [1.0.0] - 2024-01-07

The date predates this repository's git history (which starts on 2026-01-20) and cannot be
verified.

### Added
- Initial release of Cortex
- Core agent functionality with Ollama integration
- File I/O tools (read_file, write_file)
- Command execution tool
- File search and listing tools
- Git integration tools (status, diff, commit, log)
- Test execution tool (auto-detects pytest/unittest)
- Permission system (normal, auto-approve, plan modes)
- Session persistence (save/load conversations)
- Configuration system with YAML support
- Context window management with intelligent truncation
- Streaming responses (experimental)
- Security features (path traversal protection, dangerous command blocking)
- Rich terminal UI with syntax highlighting
- REPL interface with keyboard shortcuts
- Comprehensive test suite
- CI/CD pipeline
- Documentation

### Security
- Path traversal protection for all file operations
- Dangerous command detection and blocking
- Permission system to prevent unauthorized changes

### Performance
- Context window optimization
- Token counting and history truncation
- Retry logic with exponential backoff
