# Roadmap

Only things that are not done yet are listed as plans. What has been done is in
[CHANGELOG.md](../CHANGELOG.md); what works today is in [STATUS.md](STATUS.md). Items are ordered
by how much they help a user for the effort, not by date; none has a promised release.

## Next: finish what is half done

1. **Run the ablation.** The benchmark can switch planning, memory and metacognition on and off
   and repeat each setting ([BENCHMARK.md](BENCHMARK.md)). It has not been run, because it takes
   about 480 real model runs. Until it has, the defaults (all three off) are a conservative guess,
   and the retrieval threshold (`semantic_memory.min_similarity`) is a starting value. The result
   decides what stays, what is made default, and what is removed.
2. **Grow the type-checked set.** `mypy` blocks on a list of modules in `pyproject.toml`; the
   rest of `cortex/` has known type errors. Move files into the list as they are fixed.
3. **Audit routing, delegation and subagents,** which the recent work did not cover.
4. **Decide the Go and Rust layers' future.** The Go services have no Python client; the Rust
   layer's speed-up is unmeasured and its AST parser is unused. Either measure and wire them in,
   or archive them.

## Then: things users would notice

Ranked by value for effort; rough sizes are in working days.

| Idea | What it gives you | Size |
|------|-------------------|------|
| Verify after every edit | After each change the agent runs your project's tests, lint or type check and reads the result, and stops only when they pass, configured by a file in the repo | 3 to 4 |
| Trace and replay | Every model call and tool result written to a file that can be replayed against the fake provider, so any bug report becomes a reproducible test | 2 to 3 |
| Task branches and `/diff` | Each task on its own git branch, with every change shown before you accept it | 2 |
| An OpenAI-compatible provider | One provider that takes a base URL and a key, covering OpenAI and local servers (vLLM, LM Studio, llama.cpp). Would make the old OpenAI claim true | 1 to 2 |
| Cost meter | Tokens, cache hits and dollars per turn (token usage is already reported by providers) | 1 to 2 |
| Headless mode with a structured result | `cortex run --task ... --json` with budgets and a diff or pull request as output, so CI can use it | 4 to 5 |
| Repo map | A token-limited outline of the project's files and symbols, so the agent finds code in a large repository without reading files | 5 to 7 |
| Offline bundle | One command that downloads the tokenizer and embedding model so air-gapped use works from the first run | 1 to 2 |
| Secrets redaction and an audit log | Mask keys in tool output, ask before reading `.env` files, keep an append-only log of every action | 2 to 3 |
| An MCP client, then server | Use existing tool servers; expose Cortex's refactoring and memory to other tools | 9 to 12 |

## Later: more than one agent

Only if the benchmark shows a gain; a single agent with good tools and tests is the baseline to
beat, and most coding tasks have little that can safely run in parallel.

1. **Prerequisites**: agent state that is not global, cheap construction, per-agent budgets.
2. **Read-only helpers**: several explore, search and review helpers at once, each with a tool
   allowlist, a timeout and a token cap, returning findings. Success: the same pass rate with
   less main-context use or time.
3. **Isolated writers**: one worker per independent branch of a plan, each in its own git
   worktree with a declared file scope, merged one at a time behind a test gate.
4. **Roles as configuration** (architect, coder, security): a prompt, a tool allowlist and a model
   in a file, not new code.
5. **Shared notes**: a per-task notebook of distilled findings, not raw transcripts.

## Not planned

IDE integrations and an LSP server, a web UI, and "unsupervised autonomy" are not on this list.
Earlier versions of this file included them with performance targets (such as a startup time)
that nothing measured.
