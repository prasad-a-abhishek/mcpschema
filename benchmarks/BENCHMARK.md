# mcpschema — Benchmark Report

## Environment

- Python: `3.11.15`
- Platform: `Linux-6.12.67-linuxkit-aarch64-with-glibc2.41`
- Architecture: `aarch64`
- Timing methodology: `time.perf_counter()`
- Memory methodology: `tracemalloc`
- Iterations per workload: `5`

## Methodology

Each workload runs `convert_all(tools, provider)` 5 times. Mean and P95 wall-clock are reported in microseconds. Peak memory is measured with `tracemalloc` and reported in KiB.

The 'hand-written' baseline is the de-facto pattern every developer reaches for when integrating MCP with an LLM provider (per GitHub issue [`modelcontextprotocol/python-sdk#235`](https://github.com/modelcontextprotocol/python-sdk/issues/235)) — a one-off function that copies fields by hand. This is the no-library alternative mcpschema replaces.

## Workloads

| # | Description |
|---|---|
| 1 | 1 tool, 1 param, OpenAI |
| 2 | 1 tool, 5 params, OpenAI |
| 3 | 1 tool, 20 params, OpenAI |
| 4 | 1 tool, 1 param, Anthropic |
| 5 | 1 tool, 5 params, Anthropic |
| 6 | 1 tool, 20 params, Anthropic |
| 7 | 1 tool, 1 param, Gemini |
| 8 | 1 tool, 5 params, Gemini |
| 9 | 50 tools, OpenAI batch |
| 10 | 50 tools, Anthropic batch |

## Results

| Workload | mcpschema mean (µs) | mcpschema P95 (µs) | mcpschema peak (KiB) | Hand-written mean (µs) | Hand-written P95 (µs) | Hand-written peak (KiB) | Verdict |
|---|---|---|---|---|---|---|
| 1 tool, 1 param, OpenAI | 3.9 | 6.1 | 0 | 1.9 | 2.5 | 1 | hand-written (105% faster) |
| 1 tool, 5 params, OpenAI | 2.4 | 2.7 | 0 | 1.6 | 1.8 | 2 | hand-written (50% faster) |
| 1 tool, 20 params, OpenAI | 2.1 | 2.3 | 0 | 2.5 | 2.7 | 5 | mcpschema (16% faster) |
| 1 tool, 1 param, Anthropic | 2.1 | 2.5 | 0 | 1.4 | 2.0 | 1 | hand-written (50% faster) |
| 1 tool, 5 params, Anthropic | 1.9 | 2.0 | 0 | 1.4 | 2.0 | 1 | hand-written (36% faster) |
| 1 tool, 20 params, Anthropic | 2.1 | 2.7 | 0 | 2.3 | 2.5 | 4 | mcpschema (9% faster) |
| 1 tool, 1 param, Gemini | 2.0 | 2.3 | 0 | 1.7 | 2.2 | 1 | hand-written (18% faster) |
| 1 tool, 5 params, Gemini | 2.0 | 2.6 | 0 | 1.7 | 2.4 | 2 | hand-written (18% faster) |
| 50 tools, OpenAI batch | 21.3 | 21.9 | 30 | 34.1 | 43.1 | 85 | mcpschema (38% faster) |
| 50 tools, Anthropic batch | 18.9 | 26.5 | 21 | 30.0 | 30.1 | 76 | mcpschema (37% faster) |

## Trade-Off Transparency

Per Invariant 14, we publish *all* workload outcomes — including where the hand-written baseline wins. Both implementations produce functionally identical output; the difference is overhead.

**Honest scope statement**: mcpschema solves *"zero-dependency MCP tool schema → LLM provider conversion for Python 3.11+"*. It is not "faster than every alternative on every workload." It is a focused, well-tested library; performance is a means to that end.

## Replication

Run from the repo root:

```bash
python benchmarks/run_benchmark.py
```

The script is self-contained (per Invariant 22) — it imports mcpschema from the local `src/` tree and bootstraps the comparison baseline inline. No external dependencies are fetched.
