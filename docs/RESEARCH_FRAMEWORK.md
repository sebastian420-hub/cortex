# Research framework (superseded)

Earlier versions of this repository described a "Research Framework": a `research/` directory
with a challenge bank, sandboxed experiment runner and a "correction latency" measure. **It was
never committed and does not exist.**

What exists instead is the benchmark in `bench/`: 20 tasks judged by their own tests, with
steps, tokens and cost recorded per run, and an ablation mode for comparing the agent's optional
features. See [BENCHMARK.md](BENCHMARK.md).
