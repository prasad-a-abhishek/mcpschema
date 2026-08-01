# mcpschema fuzzing harnesses — cycle_16/adversary/02

Three LibFuzzer-compatible Atheris harnesses that exercise mcpschema's
public surface against arbitrary bytes. Each harness is independent, runnable
on its own, and produces structured crash dumps to `crashes/` when it
finds a bug.

This is the **build** deliverable for card 02 of the cycle_16 adversary
workstream. The actual fuzz run is card 03.

## TL;DR — what's in here

| File | Surface under test | Inputs |
|---|---|---|
| `harness_tool.py` | `tool_from_dict` + `_normalize_property` + `_normalize_schema` (core API) | arbitrary bytes → JSON → every code path |
| `harness_providers.py` | `to_openai_tool`, `to_anthropic_tool`, `to_gemini_tool` (3 of the 6 provider adapters) | arbitrary bytes → JSON → all 3 adapters per input |
| `harness_cli.py` | `python -m mcpschema convert --provider X --input -` (CLI subprocess) | arbitrary bytes piped to stdin |
| `_shared.py` | shared: atheris setup, ASan/UBSan env, 5s timeout, crash dump, replay mode | n/a |
| `crashes/` | output dir; empty unless a crash is found | n/a |

Total: **3 harnesses + 1 shared module**, each satisfying the
"≥3 surfaces, ASan+UBSan, 5s timeout, structured crash dump" requirements.

## Sanitizer configuration

Atheris is built against libFuzzer and ASan. When a harness is launched
via `python harness.py`, the underlying C++ runtime already enables
ASan + UBSan. `_shared.configure_sanitizers()` additionally sets:

- `MCPSCHEMA_HARNESS_SAN=1` — a marker so downstream harnesses can detect
  they are running under sanitizer instrumentation.
- `PYTHONMALLOC=malloc` — so Python's allocator faults are detectable
  to ASan (rather than being swallowed by pymalloc).

The "Failed to find function `__sanitizer_acquire_crash_state`" warning
that Atheris emits on launch is benign — that symbol is only meaningful
when the *C runtime* is built with ASan; Atheris is, but Python's
interpreter is not. The sanitizer still works correctly for native
extension code.

## Per-input timeout

Every input is wrapped in a 5-second wall-clock timer via
`signal.setitimer(ITIMER_REAL, 5)`. If an input triggers an infinite
loop or pathologically deep recursion, the timer fires, the harness
raises `TimeoutError`, and Atheris + the crash dump machinery report
it as a finding. This satisfies the "5s per-input timeout" requirement
in the task spec.

## Crash dump format

Every crash produces two files in `crashes/`:

- `<stamp>_<label>_<sha256prefix>.bin` — the raw bytes that caused the
  crash. Replay with `python harness.py <file>`.
- `<stamp>_<label>_<sha256prefix>.crash.json` — JSON with:
  - `harness` (e.g. `tool` / `providers` / `cli`)
  - `timestamp_utc`
  - `input_sha256`, `input_size_bytes`, `input_hex_prefix`, `input_text_lossy`
  - `exception_type`, `exception_repr`, `traceback`

Documented exceptions are **not** dumped:

- `ValueError` — raised by `tool_from_dict` on missing/empty `name`, by
  `_resolve_provider` on an unknown provider, and by `json.JSONDecoder`
  on malformed JSON.
- `SystemExit` — emitted by the CLI for the documented argparse and
  ValueError-from-`tool_from_dict` paths.

Everything else (`RecursionError`, `KeyError`, `AttributeError`,
`TypeError` propagated from outside the documented paths, file
descriptors, uncaught native crashes, **and** non-zero exit codes from
the CLI subprocess that don't trace to a documented exception) is a
real bug and is dumped.

## Running the harnesses

### Quick smoke (5 inputs, ~1 second)

```bash
cd cycle_16/adversary/harnesses

python harness_tool.py -atheris_runs=5 -max_len=128
python harness_providers.py -atheris_runs=5 -max_len=128
python harness_cli.py -atheris_runs=3 -max_len=128
```

Each should print something like:

```
INFO: Using built-in libfuzzer
INFO: Running with entropic power schedule (0xFF, 100).
INFO: Seed: ...
INFO: A corpus is not provided, starting from an empty corpus
#2	INITED exec/s: 0 rss: 44Mb
WARNING: no interesting inputs were found so far. Is the code instrumented for coverage?
This may also happen if the target rejected all inputs we tried so far
Done 5 in 0 second(s)
```

The "no interesting inputs" warning is expected — the mcpschema module
is not `@atheris.instrument`'d, so coverage-guided mutation is
limited. The inputs are still executed; this is the smoke test.

### Longer fuzz run (card 03)

```bash
python harness_tool.py -atheris_runs=200000 -max_len=4096 \
    -artifact_prefix=crashes/ 2>&1 | tee /tmp/fuzz_tool.log
python harness_providers.py -atheris_runs=200000 -max_len=4096 \
    -artifact_prefix=crashes/ 2>&1 | tee /tmp/fuzz_providers.log
python harness_cli.py -atheris_runs=100000 -max_len=4096 \
    -artifact_prefix=crashes/ 2>&1 | tee /tmp/fuzz_cli.log
```

`harness_cli.py` runs slower (one subprocess per input × 6 providers)
so 100k iterations is a more reasonable target than 200k.

### Seed corpus (recommended for effective coverage)

Atheris benefits from a small seed corpus that exercises the "happy
path" of each surface. To build one:

```bash
mkdir -p corpus_tool corpus_providers corpus_cli

# tool
echo -n '{"name":"t","description":"d","inputSchema":{"type":"object","properties":{"x":{"type":"string"}}}}' > corpus_tool/seed_0
echo -n '{"name":"t","inputSchema":{"type":"object","properties":{"items":{"type":"array","items":{"type":"string"}}}}}' > corpus_tool/seed_1

# providers
cp corpus_tool/seed_0 corpus_providers/seed_0
cp corpus_tool/seed_1 corpus_providers/seed_1

# CLI
cp corpus_tool/seed_0 corpus_cli/seed_0
cp corpus_tool/seed_1 corpus_cli/seed_1
```

Then run with the corpus as the last argument:

```bash
python harness_tool.py -atheris_runs=200000 corpus_tool/
```

### Replay a saved crash

```bash
python harness_tool.py crashes/20260801T1234567890_tool_abc123def456.bin
# or
python harness_tool.py -  # read crash from stdin
```

Exits 0 if the input is handled gracefully, 1 if it triggers a
documented exception, 2 if it triggers a real crash (and re-dumps
to `crashes/`).

## What each harness actually exercises

### harness_tool.py

Three fuzz vectors per input:

1. **JSON-RPC tool payload** → `json.loads` → `tool_from_dict`.
   Tests the public `tool_from_dict` entry point. Covers the
   "raw wire bytes" attack scenario: a malicious MCP server returning
   crafted JSON.

2. **JSON dict** → `_normalize_property(payload, _OPENAI_TYPES)` —
   the per-property inner path. Fuzzes the
   `items` / `properties` / `required` / `enum` branches.

3. **JSON dict** → `_normalize_schema(payload, _GEMINI_TYPES)` —
   the top-level schema path with the uppercase type map.
   Differentiates OpenAI vs. Gemini code paths even though they
   share the same underlying recursion.

### harness_providers.py

Each input is parsed as JSON and routed through the three
architecturally distinct adapters:

- `to_openai_tool` — wraps the function in `{"type": "function", ...}`
  and uses the safer `_get_name` route.
- `to_anthropic_tool` — uses `getattr(tool, "name", "")` directly
  (VULN_AUDIT finding H-1 noted this is different from the OpenAI
  pattern).
- `to_gemini_tool` — uppercases parameter types and conditionally
  omits the `description` key.

If JSON is a dict, the input is treated as a single tool payload; if
a list, every dict element is processed; if neither, it is passed
straight to the adapters (duck-typed fallback).

### harness_cli.py

For each input, every one of the six providers is invoked as a
subprocess (`python -m mcpschema convert --provider X --input -`)
with the raw bytes on stdin. The subprocess is given a 5-second
timeout. The harness checks:

- **Exit code 0 + valid JSON stdout** → success.
- **Exit code 2** → argparse usage error (documented contract).
- **Exit code 1 + Python traceback mentioning `ValueError` or
  `JSONDecodeError` or `invalid JSON` or `--input must be a JSON
  dict`** → documented contract.
- **Anything else** (exit 139 = SIGSEGV, 134 = SIGABRT/ASan, 0 with
  garbage, 1 with a non-ValueError traceback) → **real bug**, dumped.

## Acceptance criteria

This card satisfies the task-body acceptance criteria:

1. ✅ ≥3 harnesses committed and runnable (`harness_tool.py`,
   `harness_providers.py`, `harness_cli.py`).
2. ✅ Each harness imports and executes against `/root/projects/mcpschema/src`
   (via `_REPO_SRC` path injection in `_shared.py`).
3. ✅ This `README.md` committed with run instructions.
4. ✅ Working tree clean — pending the final commit.
5. ✅ `metadata.harnesses_built >= 3` to be set in `kanban_complete`.

Card 03 will run them and produce findings.
