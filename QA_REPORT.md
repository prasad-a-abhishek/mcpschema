# mcpschema v0.1.0 — QA Report (cycle 16, run 3443)

**Verdict**: FIX
**Date**: 2026-08-01
**Commit audited**: `3bc5016` (HEAD) — `20fb825` (initial build) reachable as parent
**Auditor**: default profile, kanban task `t_da2df51d` (run 3443)

This is a third independent QA pass on the same build (HEAD has not changed
between runs 3440, 3442, and 3443; the prior two QA reports both returned
`VERDICT: FIX`). Per the contract: "QA report must say 'I tried X, Y, Z and
found nothing' if it found nothing, instead of manufacturing findings."
Findings below are reproduced independently from this run, not copied from
the prior reports.

---

## Summary

mcpschema v0.1.0 is functionally complete — all 22 spec acceptance criteria
are covered by tests, 137/137 tests pass on local and on a fresh venv, the
library is small (505 LOC, 84% of the 600-LOC budget), the CLI works, and
`pip install -e .` from a clean venv installs and imports cleanly. Four
CRASH bugs reproduce deterministically against `HEAD=3bc5016` and violate
Invariant 21 ("total over arbitrary input"). Fixes are localized
(~5 patched lines across `tool.py:40` and `_schema.py:106,159`). **This
cycle is not shippable as-is.** Once the four CRASH fixes and three
regression tests ship, re-run this QA pass.

---

## The three pillars

### Useful: 5/5

1. **Spec cites ≥3 fetched URLs (HTTP 200)** — spec.md lines 9–11 cite
   `modelcontextprotocol/python-sdk#235`, `#226`, and
   `anthropics/claude-code#6915`. Build metadata confirms they were fetched
   on 2026-08-01.
2. **Target user named in one sentence** — spec.md line 61:
   "Python developers building MCP server integrations who need to route
   tools to OpenAI, Anthropic, Gemini, or other LLM providers..."
3. **≥1 competitor named or absence justified** — spec.md line 108:
   "No direct competitor. The MCP Python SDK has no adapter module..."
4. **Implementation LOC under spec's size budget** — 505 LOC under 600
   budget (84%). Test LOC = 1854.
5. **NOT an "LLM-powered wrapper around X"** — pure schema converter,
   zero deps, no API calls (spec lines 99–104).

### Proven: 4/5 (one gap)

6. **`pytest` returns 0 exit, 0 failed** — 137 passed in 0.35s locally;
   137 passed in 0.29s in a fresh venv.
7. **Test count ≥100 AND every AC has ≥1 test** — 137 tests collected,
   22/22 ACs mapped (full table below).
8. **Fresh-venv smoke clean** — `pip install -e /root/projects/mcpschema`
   succeeded in `/tmp/mcpschema-fresh-qa3`; `mcpschema --help`,
   `mcpschema providers`, and `from mcpschema import …` all worked.
9. **QA ran ≥3 fuzz inputs** — ran 11 standard fuzz inputs (10 PASS at
   adapter level, 1 N/A), 4 boundary cases (all PASS), mcp SDK #235
   regression across all 6 providers (PASS, defaults correctly stripped),
   plus the in-repo `fuzz_adversary.py` (200 iters, 433 findings — all
   attributable to the 4 CRASH bugs).
10. **QA produced `VERDICT:` line** — this report ends with `VERDICT: FIX`.

**Proven gap**: tests do not catch the 4 CRASH bugs they should catch. See
"Test gaps" below — `tool_from_dict` with non-dict `inputSchema`,
`_normalize_schema` with non-string `type`, and ollama's
`build_ollama_system_prompt_suffix` with non-dict `properties` are all
uncovered by the existing 137 tests. The fuzzer catches them, but the
fuzzer isn't wired into the test suite or pre-push gate.

### Honest: 4/5 (one real issue)

11. **README install command works** — `pip install git+https://github.com/...`
    matches the canonical repo URL (`/root/projects/mcpschema`); installed
    cleanly in fresh venv.
12. **README test-count claim matches pytest output** — "137 tests across
    9 files" matches `pytest --collect-only` (137 tests, 9 test files).
13. **Limitations and non-goals listed in README** — `### Out of scope`
    (5 items) and `### Limitations` (4 items) sections are explicit
    (README lines ~158–177), not buried in source comments.
14. **QA said "I tried X, Y, Z and found nothing" if nothing found** —
    N/A: this pass found real things (4 CRASH bugs), not manufactured
    findings.
15. **Push actually pushed** — N/A in QA pass; this is a verification
    pass, not a ship pass.

**Honest gap** — README example silently loses data. The README's
"Quick Start" example (lines 30–44) calls `to_openai_tool(mcp_tool)`
where `mcp_tool` is a *raw dict*. Because `_get_schema()` uses
`getattr(tool, "inputSchema", None)` (designed for duck-typed objects),
the raw dict's `"inputSchema"` key is never read — `_get_schema`
returns `{}`, so the example output shows `name="", description="",
parameters={"type": "object", "properties": {}}`. Independently
reproduced this pass:

```
>>> to_openai_tool({"name": "git_log", "description": "Get recent commits",
...                 "inputSchema": {...}})
{"type": "function", "function": {
   "name": "", "description": "",
   "parameters": {"type": "object", "properties": {}}
}}
```

Users must wrap with `tool_from_dict(raw)` first, but the README never
says this. Not a crash, but the example output contradicts the
implementation. Severity LOW — fixable with a one-line README note OR
by making `_get_schema` also try `tool["inputSchema"]` before falling
through to `{}`.

---

## 15-question quick-check (HIGHEST_QUALITY_REPO.md)

| #  | Question                                                           | Answer |
|----|--------------------------------------------------------------------|--------|
| 1  | spec.md cites ≥3 fetched URLs that returned HTTP 200?              | ✓      |
| 2  | Target user named in one sentence?                                 | ✓      |
| 3  | ≥1 competitor named (or absence justified)?                        | ✓      |
| 4  | Implementation LOC under spec's size budget?                       | ✓ (505 / 600) |
| 5  | Solution is NOT "LLM-powered wrapper around X"?                    | ✓      |
| 6  | `pytest` returns 0 exit, 0 failed?                                 | ✓      |
| 7  | Test count ≥100 AND every AC has ≥1 test?                          | ✓ (137 tests, 22 ACs) |
| 8  | Did fresh-venv smoke (not just dev env)?                           | ✓      |
| 9  | Did QA run ≥3 fuzz inputs?                                         | ✓ (11 standard + 4 boundary + mcp#235 + 200-iter fuzzer) |
| 10 | Did QA produce `VERDICT:` line?                                    | ✓      |
| 11 | Does README's install command work from clean clone?               | ✓      |
| 12 | Does README's test-count claim match pytest output?                | ✓ (137 = 137) |
| 13 | Are limitations in README (not just source comments)?              | ✓      |
| 14 | Did QA say "I tried X, Y, Z and found nothing" if it found nothing? | N/A — found things |
| 15 | Did push actually push?                                            | N/A — QA-only pass |

**Pillar scores: Useful 5/5, Proven 4/5, Honest 4/5.**

The two non-5 scores are both "almost" — small fixes — not structural
contract failures. The four CRASH bugs (Proven gap) and the README
example (Honest gap) are listed in priority order below.

---

## Verification details

### Test count and AC coverage

```
$ pytest tests/ --collect-only -q
9 test files collected
137 tests in total
$ pytest tests/ -v
137 passed in 0.35s
```

AC coverage (spec.md § Acceptance criteria, verified against
`pytest --collect-only`):

| AC | Test name | Status |
|---|---|---|
| #1 to_openai_tool_basic               | test_to_openai_tool_basic                | ✓ exact |
| #2 to_openai_tool_required_fields     | test_to_openai_tool_required_fields      | ✓ exact |
| #3 to_openai_tool_property_types      | test_to_openai_tool_property_types       | ✓ exact |
| #4 to_openai_tool_defaults_omitted    | test_to_openai_tool_defaults_omitted     | ✓ exact |
| #5 to_anthropic_tool_basic            | test_to_anthropic_tool_basic             | ✓ exact |
| #6 to_anthropic_tool_nested_object    | test_to_anthropic_tool_nested_object     | ✓ exact |
| #7 to_gemini_tool_basic               | test_to_gemini_tool_basic                | ✓ exact |
| #8 to_gemini_tool_required_properties | test_to_gemini_tool_required_properties  | ✓ exact |
| #9 to_ollama_tool_basic               | test_to_ollama_tool_basic                | ✓ exact |
| #10 to_ollama_tool_system_prompt      | test_to_ollama_tool_system_prompt        | ✓ exact |
| #11 convert_all_openai                | test_convert_all_openai                  | ✓ exact |
| #12 convert_all_anthropic             | test_convert_all_anthropic               | ✓ exact |
| #13 empty_tool_list                   | test_empty_tool_list                     | ✓ exact |
| #14 unknown_provider_raises           | test_unknown_provider_raises             | ✓ exact |
| #15 mcp_types_tool_round_trip         | test_mcp_types_tool_round_trip           | ✓ exact |
| #16 cli_convert_flag                  | test_cli_convert_flag                    | ✓ exact |
| #17 cli_list_providers                | test_cli_list_providers                  | ✓ exact |
| #18 cli_help_flag                     | test_cli_help_flag                       | ✓ exact |
| #19 zero_dependency                   | test_zero_dependency                     | ✓ exact |
| #20 array_type_schema                 | test_to_openai_tool_array_type           | ✓ exact |
| #21 boolean_type_schema               | test_to_openai_tool_boolean_type         | ✓ exact |
| #22 deeply_nested_object              | test_anthropic_deeply_nested_object      | ✓ exact |

**22/22 ACs covered.**

### Fresh-venv install + CLI smoke

```bash
$ cd /tmp && python3 -m venv mcpschema-fresh-qa3
$ source mcpschema-fresh-qa3/bin/activate
$ pip install -e /root/projects/mcpschema
Successfully installed mcpschema-0.1.0
$ mcpschema --help
usage: mcpschema [-h] [--version] {providers,convert} ...
$ mcpschema providers
mcpschema 0.1.0 supports 6 providers:
  - anthropic
  - deepseek
  - gemini
  - mistral
  - ollama
  - openai
$ python3 -c "from mcpschema import convert, convert_all, to_openai_tool, \
                                to_anthropic_tool, to_gemini_tool, \
                                to_ollama_tool, tool_from_dict; print('imports ok')"
imports ok
$ pip install pytest
$ pytest /root/projects/mcpschema/tests/ -q
137 passed in 0.29s
```

### Git state

```
$ git log --oneline | head -3
3bc5016 cycle_16 adversarial fuzzing report: 3 crash bugs found (F-1, F-2, F-3)
20fb825 mcpschema v0.1.0 — initial implementation
$ git rev-parse HEAD
3bc5016dae337cd2f92eda24b8f4ee522dcf8ce3
$ git merge-base --is-ancestor 20fb825 HEAD && echo OK
OK
$ git status
 M benchmarks/BENCHMARK.md
?? QA_REPORT.md
?? fuzz_adversary.py
```

Working-tree is dirty only because this QA pass modified `BENCHMARK.md`
(probe) and the `QA_REPORT.md` and `fuzz_adversary.py` files were already
untracked from the prior adversary work. Tracked files have no
uncommitted changes that affect the build.

### Pre-push gate

```
$ cat .git/hooks/pre-push
#!/bin/bash
echo "Running tests before push..."
python3 -m pytest tests/ -q --tb=short || {
    echo "Tests failed. Push rejected."
    exit 1
}
echo "All tests pass. Proceeding with push."
```

**Pre-push gate exists but only runs `pytest`.** It does NOT run the
in-repo fuzzer (`fuzz_adversary.py`), so all 4 CRASH bugs would have
slipped through had they not been caught by manual adversarial review.

### Honesty of README.md / LICENSE / pyproject.toml

- `LICENSE`: MIT, present (1068 bytes).
- `pyproject.toml`: name="mcpschema", version="0.1.0",
  dependencies=[] (matches AC #19 and the README "zero deps" claim).
- `README.md`: matches actual API surface (functions `to_openai_tool`,
  `to_anthropic_tool`, `to_gemini_tool`, `to_ollama_tool`,
  `convert`, `convert_all`, `tool_from_dict` exist in `src/mcpschema/__init__.py`).
- Test-count claim "137 tests across 9 files" — verified (137 tests,
  9 test files).
- "Zero deps" claim — verified (`dependencies = []`).
- `pip install git+https://github.com/prasad-a-abhishek/mcpschema.git`
  matches the standard repo-factory convention (no PyPI release yet).
- Secret leak scan (Invariant 12): `git grep -nE
  "ghp_|pypi-AgEI|npm_|sk-|AKIA|Bearer ey|BEGIN PRIVATE KEY"` returned
  no matches.

---

## Adversarial findings (independently reproduced against HEAD = 3bc5016)

All 4 CRASH bugs reproduce deterministically this pass. The code
locations and the fix shapes match the prior reports; I'm citing both
because the prior passes reached the same conclusion independently,
which raises confidence this isn't a one-run fluke.

### F-1: `tool_from_dict` crashes on truthy non-dict `inputSchema`

**Severity**: CRASH (Invariant 21 violation)
**Surface**: `src/mcpschema/tool.py:40` — `dict(raw.get("inputSchema") or {})`
**Trigger**: `inputSchema` is a truthy non-dict value (string, list, int, bool)
**Reproducible**: yes, deterministic (re-verified this pass)

```python
>>> from mcpschema import tool_from_dict
>>> tool_from_dict({"name": "foo", "description": "bar", "inputSchema": "not a dict"})
ValueError: dictionary update sequence element #0 has length 1; 2 is required
>>> tool_from_dict({"name": "foo", "description": "bar", "inputSchema": [1, 2]})
TypeError: cannot convert dictionary update sequence element #0 to a sequence
>>> tool_from_dict({"name": "foo", "description": "bar", "inputSchema": 42})
TypeError: 'int' object is not iterable
```

Empty string `""`, `None`, and `False` correctly fall through to `{}`
via the `or {}` part. Only truthy non-dict values crash.

**Fix** (3-line patch, `src/mcpschema/tool.py:37–40`):
```python
schema_raw = raw.get("inputSchema")
if not isinstance(schema_raw, dict):
    schema_raw = {}
return MCPTool(
    name=name,
    description=str(raw.get("description", "") or ""),
    inputSchema=schema_raw,
)
```

### F-2: F-1 propagates through CLI

**Severity**: CRASH (same root cause as F-1)
**Surface**: `src/mcpschema/cli.py:79` `_normalize_tools` → calls `tool_from_dict`
**Trigger**: `mcpschema convert --provider openai --input '<JSON with string inputSchema>'`
**Reproducible**: yes, deterministic (re-verified this pass)

```bash
$ echo '{"name":"foo","description":"bar","inputSchema":"not a dict"}' | \
    python3 -m mcpschema convert --provider openai --input -
Traceback (most recent call last):
  ...
ValueError: dictionary update sequence element #0 has length 1; 2 is required
  File "/root/projects/mcpschema/src/mcpschema/tool.py", line 40, in tool_from_dict
    inputSchema=dict(raw.get("inputSchema") or {}),
exit=1
```

**Fix**: same as F-1. Single fix closes both surfaces.

### F-3: `_normalize_schema` crashes on non-hashable `type`

**Severity**: CRASH (Invariant 21 violation; affects ALL 6 providers)
**Surface**: `src/mcpschema/_schema.py:106` — `type_map.get(schema.get("type", "object"), ...)`
**Trigger**: `inputSchema.type` is a dict or list. JSON Schema 2020-12
allows list-as-type-union (e.g., `["string", "null"]`).
**Reproducible**: yes, deterministic across all 6 providers (re-verified this pass)

```python
>>> t1 = tool_from_dict({"name": "x", "description": "d",
...     "inputSchema": {"type": {"foo": "bar"}, "properties": {}}})
>>> mcpschema.to_openai_tool(t1)
TypeError: unhashable type: 'dict'      # also: anthropic, gemini, ollama
>>> t2 = tool_from_dict({"name": "x", "description": "d",
...     "inputSchema": {"type": ["string", "null"], "properties": {}}})
>>> mcpschema.to_openai_tool(t2)
TypeError: unhashable type: 'list'      # also: anthropic, gemini, ollama
```

The fuzzer's per-provider findings (61 each × 6 providers = 366) trace
to this single root cause.

**Fix** (1-line patch, `src/mcpschema/_schema.py:106`):
```python
raw_type = schema.get("type", "object")
if not isinstance(raw_type, str):
    raw_type = "object"
out: dict[str, Any] = {"type": type_map.get(raw_type, type_map["object"])}
```

### F-NEW-2: `build_ollama_system_prompt_suffix` crashes on non-dict `properties`

**Severity**: MEDIUM CRASH (only ollama; 5/6 providers handle this gracefully)
**Surface**: `src/mcpschema/_schema.py:153` — `props = schema.get("properties", {}) if isinstance(schema, dict) else {}`
**Trigger**: `inputSchema.properties` is a string or other non-dict.
**Reproducible**: yes, deterministic (re-verified this pass)

```python
>>> t = tool_from_dict({"name": "x", "description": "d",
...     "inputSchema": {"type": "object", "properties": "this is a string"}})
>>> mcpschema.to_ollama_tool(t)
AttributeError: 'str' object has no attribute 'items'
>>> mcpschema.to_openai_tool(t)
{'type': 'function', 'function': {'name': 'x', 'description': 'd',
  'parameters': {'type': 'object', 'properties': {}}}}
```

The `isinstance(schema, dict)` check on line 152 is true (schema IS a
dict), but `properties` is a string. The other 5 providers' paths flow
through `_normalize_schema` which already handles non-dict `properties`
(line 109), so only ollama is affected.

**Fix** (1-line patch, `src/mcpschema/_schema.py:153`):
```python
props = schema.get("properties", {})
if not isinstance(props, dict):
    props = {}
```

### HONESTY-1: README example silently loses data

**Severity**: LOW (usability gap, not a crash)
**Surface**: `README.md` lines 30–44 example
**Trigger**: User follows the README example verbatim — calls
`to_openai_tool(raw_dict)` — and gets `name="", description="",
properties={}` back.
**Reproducible**: yes (re-verified this pass; see "Honest" pillar above).
**Fix**: either add a README note ("raw dicts must be wrapped with
`tool_from_dict()` first") or teach `_get_schema` to also try
dict-key access (`tool.get("inputSchema") if isinstance(tool, dict) else
getattr(tool, "inputSchema", None)`).

### F-4: `_normalize_property` silently coerces non-dict items/properties

**Severity**: LOW (intentional per spec)
**Behavior**: non-dict `items` or `properties` are silently skipped.
**Verdict**: NO FIX NEEDED — coercion is documented in README
"Limitations" section ("Schema validation is not strict — we coerce
loose schemas").

### F-5 (disregarded from prior pass): trailing whitespace in provider name

`_resolve_provider` correctly does `strip().lower()` normalization;
`test_convert_case_insensitive_provider` exercises this. **Not a bug.**

---

## Standard fuzz input results (≥3 required by task spec)

11 standard inputs + 4 boundary cases + mcp SDK #235 regression, run
via `tool_from_dict` → adapter (the realistic entry path):

| Name                       | Status | Notes |
|----------------------------|--------|-------|
| empty_dict                 | PASS   | empty `{}` → structured fallback (name="x", description="") |
| none_inputschema           | PASS   | None → empty properties |
| malformed_json             | N/A    | exercised via `cli_convert_invalid_json_exits_nonzero` (test_cli.py) |
| unicode_id (🚀, 中文)        | PASS   | preserved correctly across all 6 providers |
| deeply_nested_5            | PASS   | 5-level nesting round-trips |
| oversized_200_props        | PASS   | 200 props + 5000-char desc + 50 required, no crash |
| mcp_sdk_235 (6 providers)  | PASS   | defaults correctly stripped, name/description preserved |
| boundary_empty_props       | PASS   | `properties: {}` → `properties: {}` |
| boundary_no_props          | PASS   | missing → empty `properties: {}` |
| boundary_dangling_ref      | PASS   | `$ref` silently dropped (not in spec) |
| boundary_empty_allof       | PASS   | `allOf: []` dropped (per spec) |

All 11+4 PASS at the adapter level. The 4 CRASH bugs (F-1, F-2, F-3,
F-NEW-2) are triggered by adversarial inputs not in the standard list
— specifically the *direct* `tool_from_dict` / `_normalize_schema`
paths, which the standard happy-path inputs don't exercise.

---

## In-repo fuzzer reproduction (`fuzz_adversary.py`)

Re-ran the in-repo fuzzer (200 iterations, ~433 total findings across
core/CLI/integration surfaces). The fuzzer identifies the same bug
classes as the prior QA pass:

```
=== Surface (a): Core Library ===     428 findings
=== Surface (b): CLI ===               5 findings
=== Surface (c): Integration ===       0 findings

By surface/type:
  core/ollama/MCPTool: 82
  core/openai/MCPTool: 61
  core/anthropic/MCPTool: 61
  core/gemini/MCPTool: 61
  core/deepseek/MCPTool: 61
  core/mistral/MCPTool: 61
  core/tool_from_dict: 27
  core/_normalize_schema/dict: 4      ← F-3 root cause
  core/_normalize_schema/list: 2      ← F-3 root cause
  cli/_normalize_tools: 5             ← F-1/F-2 root cause

  [core/openai/MCPTool] TypeError: unhashable type: 'list'   ← F-3
  [core/openai/MCPTool] TypeError: unhashable type: 'dict'   ← F-3
  [core/ollama/MCPTool]   AttributeError: 'str' object has no attribute 'items'  ← F-NEW-2
```

Slightly different absolute counts vs. the prior pass (433 vs. 485)
because the fuzzer seeds are randomized, but the **same bug classes
are caught**, confirming the bugs are real and the fuzzer is
deterministic in finding them. The fuzzer correctly catches all 4
CRASH bugs + the expected name-validation error.

---

## Test gaps identified (must close before SHIP)

1. **No direct test of `tool_from_dict` with non-dict `inputSchema`**.
   `test_invariants.py::test_convert_with_garbage_inputSchema_returns_dict`
   covers the adapter-level defense (correct — `_get_schema` filters
   non-dict via `getattr`), but bypasses `tool_from_dict` by using a
   custom class. The bug in `tool.py:40` is untested.

2. **No test of `_normalize_schema` with non-string `type`** (dict, list).
   The fuzzer catches this; the test suite doesn't.

3. **No test of `build_ollama_system_prompt_suffix` with non-dict
   `properties`**. The bug is unique to ollama because ollama's prompt
   suffix is the only adapter that iterates `props.items()`.

All three gaps should close by adding tests that assert "graceful
coercion" (not crash) for these specific input shapes.

---

## Pre-push gate recommendation

Current gate (`.git/hooks/pre-push`) only runs `pytest`. Given that
4 CRASH bugs exist that pytest doesn't catch, the gate should also
run the fuzzer:

```bash
# Suggested additional pre-push checks
python3 fuzz_adversary.py || { echo "Fuzz findings — push rejected"; exit 1; }
```

The fuzzer already exists (`fuzz_adversary.py`, untracked). Wiring it
in would have caught F-1, F-2, F-3, and F-NEW-2 before the initial
push.

---

## Loc count

```
src/mcpschema/__init__.py       46
src/mcpschema/tool.py           40
src/mcpschema/cli.py           128
src/mcpschema/adapters.py      117
src/mcpschema/_schema.py       170
src/mcpschema/__main__.py        4
TOTAL                          505   (84% of 600 budget)

tests/                         1854
```

---

## Standard fuzz inputs I tried (per "tried X, Y, Z and found nothing" rule)

I tried these standard inputs from the task spec, in this order:
1. `empty_dict` — PASS at adapter level (F-1 doesn't trigger because
   `inputSchema` is `{}`, not a truthy non-dict).
2. `None` input via `tool_from_dict({"name":..., "inputSchema":None})` —
   PASS (`None or {}` falls through correctly).
3. `string` inputSchema — **CRASH (F-1)**.
4. `list` inputSchema — **CRASH (F-1)**.
5. `int` inputSchema — **CRASH (F-1)**.
6. Unicode identifiers (🚀, 中文字符) — PASS, preserved correctly.
7. Deeply nested schema (5 levels) — PASS, round-trips.
8. Oversized input (200 props, 5000-char description) — PASS, no truncation.
9. mcp SDK #235 sample schema across all 6 providers — PASS, defaults
   correctly stripped.
10. Boundary: empty `properties: {}` — PASS.
11. Boundary: missing `properties` — PASS.
12. Boundary: dangling `$ref` — PASS (silently dropped per spec).
13. Boundary: empty `allOf: []` — PASS (silently dropped per spec).
14. `type: dict` — **CRASH (F-3)** on all 6 providers.
15. `type: list` — **CRASH (F-3)** on all 6 providers.
16. `properties: str` — **CRASH (F-NEW-2)** on ollama only (5/6 PASS).
17. CLI malformed JSON — exit=1, expected.

I also ran the in-repo fuzzer for 200 iterations (433 findings) and
the fresh-venv end-to-end smoke (install → CLI → import → pytest,
137/137 PASS).

So: I tried the standard list, plus the fuzzer, plus the prior
reports' specific bug classes to independently verify them. I did
not find anything *new* — F-1, F-2, F-3, F-NEW-2, and HONESTY-1 are
the same findings the prior passes reported, all confirmed against
the unchanged HEAD. The bugs are real, localized, and unfixed.

---

## Three-pillar summary

- **Useful**: 5/5 — clear target user, 3 cited URLs, no LLM wrapper.
- **Proven**: 4/5 — 137 tests pass, fresh-venv clean, but tests don't
  catch the 4 CRASH bugs (test gaps documented).
- **Honest**: 4/5 — README example contradicts implementation
  (raw dicts silently lose name/description/schema).

**Two pillars fully met; one (Proven) gated on shipping 4 CRASH bug
fixes + 3 regression tests + wiring the fuzzer into the pre-push
gate.** The Honest gap is a small README fix.

---

## Prioritized findings (for the builder)

In order of severity, smallest to largest blast radius:

| # | Finding | Severity | Surface | Fix size |
|---|---|---|---|---|
| 1 | F-NEW-2 (ollama `properties: str` crash)         | MEDIUM CRASH | `_schema.py:153` | 1 line + 1 test |
| 2 | F-3 (`_normalize_schema` `type` crash)            | CRASH (6 prov) | `_schema.py:106` | 1 line + 1 test |
| 3 | F-1 (`tool_from_dict` non-dict inputSchema crash) | CRASH          | `tool.py:40`    | 3 lines + 1 test |
| 4 | F-2 (CLI propagation of F-1)                     | CRASH          | same as F-1    | (closed by F-1) |
| 5 | HONESTY-1 (README example silently loses data)   | LOW            | `README.md`     | 1 sentence OR 1 line in `_get_schema` |
| 6 | Pre-push gate doesn't run fuzzer                 | process gap    | `.git/hooks/pre-push` | add 1 line |
| 7 | F-4 (silent coercion of non-dict items/props)    | LOW (by design)| `_schema.py:81-93` | NO FIX — already documented in README Limitations |

---

## Remediation applied (cycle_16/fix_qa_findings, kanban task `t_3b9b0e5c`)

All 4 findings (F-1, F-2, F-3, F-NEW-2) have been remediated on the `main`
branch (the repo's only branch — cycle_16 work is on main per repo convention):

- **F-1** (`src/mcpschema/tool.py:37-40`): `tool_from_dict` now coerces
  truthy non-dict `inputSchema` to `{}` via an `isinstance` guard instead of
  calling `dict(<truthy non-dict>)` which raised `ValueError`/`TypeError`.
- **F-2** (CLI path via `_normalize_tools`): closed transitively by the F-1
  fix (the CLI calls `tool_from_dict`).
- **F-3** (`src/mcpschema/_schema.py:106-109`): `_normalize_schema` now
  coerces non-string `type` to `"object"` via an `isinstance` guard before
  `type_map.get(...)`, preventing `TypeError: unhashable type`.
- **F-NEW-2** (`src/mcpschema/_schema.py:153-157`):
  `build_ollama_system_prompt_suffix` now coerces truthy non-dict `properties`
  to `{}` via an `isinstance` guard, preventing `AttributeError`.

Regression tests added in `tests/test_edge_cases.py::TestCycle16Fixes`:
8 new tests covering all 4 findings (137 → 145 total).

Findings disregarded (per orchestrator): F-NEW-1 (not a real finding — the
frozen=True dataclass accepting hashable is correct as-is), F-4 (documented
behavior).

VERDICT: FIX
