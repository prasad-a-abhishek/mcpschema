# VULN_AUDIT.md — mcpschema v0.1.0, cycle 16

**Audit target**: mcpschema v0.1.0 at commit `111a6f19ad8614a4ede070cbb56108ece9bd6a6f`
(HEAD; on top of remediation commit `25cfd7a`).
**Auditor**: `default` profile, kanban task `t_0db92405`, run 3449.
**Role**: Manual vulnerability audit of the post-fix public surface (card 01
of 5 in the cycle_16 adversary workstream).
**Methodology**: Manual source-code review + adversarial-input PoC against
every public entry point + cross-reference with prior fuzzer/QA artifacts.
**Date**: 2026-08-01.

---

## TL;DR — VERDICT

| Item | Result |
|---|---|
| Severity-ranked findings produced | ✓ 4 findings (1 High, 1 Medium, 2 Low) + 3 Info notes |
| Prior F-1/F-2/F-3/F-NEW-2 regression | ✓ still silent on every public API path |
| F-3 private-helper `type_map=None` nuance | ✓ unchanged, still raises (documented in QA_REPORT) |
| New crash-class bugs | ✗ none found |
| **Verdict** | **DIRTY → minor remediation required before FUZZING_REPORT card (card 04)** |

**DIRTY** here does NOT mean "un-shippable" — none of the findings are
crash-class. They are contract-coverage gaps that break the invariant
"every public API is total over arbitrary input" (Invariant 21) for two
of six provider adapters and the ollama prompt-suffix formatter. They
also add real-world risk for downstream LLM providers, which reject
`null` / `None` in the `name` field.

**Action requested from cycle_16 builder (future fix card)**:
- H-1: route `to_anthropic_tool` and `to_gemini_tool` through
  `_get_name` / `_get_description` instead of raw `getattr(..., "")`
  (mirror `to_openai_tool`'s pattern). One-line changes.
- M-1: harden `build_ollama_system_prompt_suffix` against non-string
  `description` on a nested property (currently silently produces a
  Python `repr()` of the value in the prompt suffix).
- L-1 + L-2: informational / cosmetic — see body.

---

## Methodology

### Surface enumeration (per task scope)

| Surface | File | Public? | Audited |
|---|---|---|---|
| `MCPTool` dataclass | `src/mcpschema/tool.py` | yes (frozen=True) | ✓ |
| `tool_from_dict(raw)` | `src/mcpschema/tool.py:29` | yes | ✓ |
| `to_openai_tool(tool)` | `src/mcpschema/adapters.py:15` | yes | ✓ |
| `to_anthropic_tool(tool)` | `src/mcpschema/adapters.py:24` | yes | ✓ |
| `to_gemini_tool(tool)` | `src/mcpschema/adapters.py:36` | yes | ✓ |
| `to_ollama_tool(tool)` | `src/mcpschema/adapters.py:52` | yes | ✓ |
| `to_deepseek_tool(tool)` | `src/mcpschema/adapters.py:64` | alias → openai | ✓ (delegated) |
| `to_mistral_tool(tool)` | `src/mcpschema/adapters.py:72` | alias → openai | ✓ (delegated) |
| `convert(tool, provider)` | `src/mcpschema/adapters.py:103` | yes | ✓ |
| `convert_all(tools, provider)` | `src/mcpschema/adapters.py:111` | yes | ✓ |
| `cli main(argv)` | `src/mcpschema/cli.py:114` | yes | ✓ |
| `cli _cmd_convert(args)` | `src/mcpschema/cli.py:90` | yes | ✓ |
| `cli _read_input(value)` | `src/mcpschema/cli.py:67` | yes | ✓ |
| `cli _normalize_tools(payload)` | `src/mcpschema/cli.py:79` | yes | ✓ |
| `_get_schema / _get_name / _get_description` | `src/mcpschema/_schema.py:36-53` | private | ✓ |
| `_normalize_property / _normalize_schema` | `src/mcpschema/_schema.py:56-124` | private | ✓ (incl. type_map=None nuance) |
| `build_openai_function / build_anthropic_input_schema / build_gemini_parameters / build_ollama_system_prompt_suffix` | `src/mcpschema/_schema.py:127-176` | private (but reachable via adapters) | ✓ |

512 LOC total across `__init__.py`, `tool.py`, `_schema.py`, `adapters.py`,
`cli.py`, `__main__.py`. Manual review covered every line.

### Adversarial-input PoC script

Independent PoC script (`/tmp/cycle16_adversary_audit_poc.py`, ~80 lines)
exercised every public surface against:

1. **Prior CRASH repros from FUZZING_REPORT.md @ 3bc5016** — 8 inputs,
   verified silent on commit 111a6f1.
2. **Standard adversarial-input list from re-QA check #9** — 8 inputs
   (empty dict, `type=int`, `type=None`, `properties=list`, `items=string`,
   unicode names, depth-7 nesting, 1MB payload), verified silent.
3. **Fresh surfaces not covered by prior QA** — `name=None` on
   duck-typed objects (the central new finding), non-string
   `description` fields, mixed-type `required` arrays,
   non-string per-property `description`, deeply-nested (N=5000)
   recursion check, CLI `convert` with `--input '-'`, `--provider`
   adversarial strings (NUL bytes, very-long names).
4. **CLI smoke** — `mcpschema convert --provider openai --input '<json>'`
   for representative adversarial payloads.

### Tools used

- Manual source-code review (no static analyzer beyond `grep` /
  `rg`).
- Python REPL PoC scripts (`/tmp/cycle16_adversary_audit_poc.py`).
- subprocess invocations of the installed `mcpschema.cli` to verify
  CLI surface.
- Cross-reference against `git show 25cfd7a` (fix), `git show 3bc5016:FUZZING_REPORT.md`
  (prior fuzz), `QA_REPORT.md` (re-QA), `FUZZING_REPORT.md` (re-fuzz).

### Threat-model lens

| Threat class | How it applies to mcpschema |
|---|---|
| **Untrusted input** | The library's primary purpose is to ingest *untrusted* MCP server output (tool descriptors that come from arbitrary MCP servers, possibly hostile). `inputSchema` is the main attack surface. |
| **Resource exhaustion** | All processing is pure-Python and CPU/memory bound by input size. No disk/network I/O. |
| **Output injection** | Output is plain dicts that the caller serializes. The Ollama adapter emits a `system_prompt_suffix` string that is concatenated into the LLM's system prompt — *this is a text-generation injection sink*. |
| **Protocol smuggling** | Output goes to provider APIs. Field names are fixed. No path-traversal, no HTTP surface. |
| **TOCTOU / aliasing** | `tool_from_dict` deep-copies `inputSchema` (`dict(raw_input)`) on construction — verified safe by mutation test. |

---

## Severity-ranked findings

| ID | Severity | Surface | CWE | One-line |
|----|----------|---------|-----|----------|
| **H-1** | **High** | `to_anthropic_tool`, `to_gemini_tool` | CWE-20 (improper input validation) | Output `name` field is `None` for duck-typed objects whose `name` attribute is present-but-None — bypasses `_get_name()`'s `isinstance(name, str)` guard. |
| **M-1** | **Medium** | `build_ollama_system_prompt_suffix` | CWE-20 | Non-string `description` on a nested property produces a Python `repr()` in the system prompt suffix (e.g. `"— ['list', 'as', 'desc']"`) — an integrity/honesty issue for the LLM prompt. |
| **L-1** | **Low** | `to_anthropic_tool`, `to_gemini_tool` | CWE-697 (incorrect comparison) | `_get_name` / `_get_description` use the typed-coercion pattern but the same pattern was NOT applied in `to_anthropic_tool` / `to_gemini_tool` — partial invariant violation across the public API. |
| **L-2** | **Low** | `tool_from_dict` | CWE-1284 (improper validation of specified quantity) | `description` field is coerced via `str(raw.get("description", "") or "")` — truthy non-string values (lists, dicts, ints other than 0) become Python `repr()` strings instead of being rejected as invalid input. |
| INFO-1 | Info | `_normalize_schema` | — | Private-helper `type_map=None` still raises `AttributeError`. Public-API path is silent. (Already documented in QA_REPORT.md.) |
| INFO-2 | Info | `convert_all` | — | Accepts any iterable including non-list iterables (dict iterates over keys, string iterates over chars). Behavior is silent but the use case is unexpected. |
| INFO-3 | Info | `MCPTool` | — | `frozen=True` is bypassable via `object.__setattr__(...)` — Python-language wart, not a library vulnerability. |

**0 Critical, 1 High, 1 Medium, 2 Low, 3 Info.**

---

## Per-finding narratives

### H-1 — `to_anthropic_tool` / `to_gemini_tool` leak `None` as the `name` field

**Severity**: High
**CWE**: CWE-20 (Improper Input Validation)
**File / line**: `src/mcpschema/adapters.py:30, 44` (anthropic, gemini)
**Public surface affected**: `to_anthropic_tool`, `to_gemini_tool`
**Reachable via**: direct call, `convert(..., "anthropic"|"gemini")`,
`convert_all([...], "anthropic"|"gemini")`, `cli convert --provider anthropic|gemini`.

#### Description

`to_openai_tool` and `to_ollama_tool` route the tool's `name` and
`description` through the type-coercing helpers `_get_name` /
`_get_description` in `_schema.py`, which return `""` for any input
that is missing, `None`, or non-string. This satisfies Invariant 21
("library functions must be total over arbitrary input").

`to_anthropic_tool` and `to_gemini_tool` use a *different* pattern —
raw `getattr(tool, "name", "")` — which only falls back to `""` when
the attribute is **missing**, not when it is present-but-None.

#### Attack / PoC

```python
from mcpschema import to_anthropic_tool, to_gemini_tool

class MalformedTool:
    name = None       # present but None
    description = None
    inputSchema = {}

print(to_anthropic_tool(MalformedTool()))
# {'name': None, 'description': '', 'input_schema': {'type': 'object', 'properties': {}}}

print(to_gemini_tool(MalformedTool()))
# {'name': None, 'parameters': {'type': 'OBJECT', 'properties': {}}}
```

For comparison, the same input through `to_openai_tool` produces
`{'name': '', ...}` (the documented coercion behavior).

#### Why this matters

- The Anthropic API requires a string `name` (and will reject `None` /
  raise a 400 on most SDK paths). A caller who passes a duck-typed
  MCP tool whose `name` is somehow `None` (which happens when an MCP
  server returns a malformed tool descriptor — a known pattern in the
  wild) will receive an adapter output that will fail at the API
  boundary.
- Same for Gemini's `name` field.
- This silently breaks Invariant 21 for 2 of 6 provider adapters.

#### Fix

Replace the raw `getattr(...)` calls in `to_anthropic_tool` and
`to_gemini_tool` with the same `_get_name` / `_get_description`
helpers that `to_openai_tool` uses:

```python
# src/mcpschema/adapters.py:24-49
from mcpschema._schema import _get_name, _get_description

def to_anthropic_tool(tool: Any) -> dict[str, Any]:
    name = _get_name(tool)
    desc = _get_description(tool)
    out: dict[str, Any] = {
        "name": name,
        "input_schema": build_anthropic_input_schema(tool),
    }
    if desc:
        out["description"] = desc
    return out

def to_gemini_tool(tool: Any) -> dict[str, Any]:
    name = _get_name(tool)
    desc = _get_description(tool)
    out: dict[str, Any] = {
        "name": name,
        "parameters": build_gemini_parameters(tool),
    }
    if desc:
        out["description"] = desc
    return out
```

One-line behavioral change per adapter; no API breakage (the output
is still a dict with the same keys; `None` becomes `""`).

#### Regression test

Add to `tests/test_edge_cases.py`:

```python
def test_anthropic_tool_with_name_none_returns_empty_string():
    class T:
        name = None
        description = None
        inputSchema = {}
    out = to_anthropic_tool(T())
    assert out["name"] == ""
    assert out["description"] == ""

def test_gemini_tool_with_name_none_returns_empty_string():
    class T:
        name = None
        description = None
        inputSchema = {}
    out = to_gemini_tool(T())
    assert out["name"] == ""
    assert out["description"] == ""
```

---

### M-1 — Non-string `description` on a nested property leaks Python `repr()` into the Ollama system prompt suffix

**Severity**: Medium
**CWE**: CWE-20 (Improper Input Validation)
**File / line**: `src/mcpschema/_schema.py:170-175` (build_ollama_system_prompt_suffix)
**Public surface affected**: `to_ollama_tool`, `convert(..., "ollama")`,
`convert_all([...], "ollama")`, `cli convert --provider ollama`.

#### Description

`build_ollama_system_prompt_suffix` reads each property's `description`
without an `isinstance(..., str)` guard, then concatenates it into the
suffix with an f-string. For non-string values, the f-string calls
`repr()` implicitly — so a list `["list", "as", "desc"]` becomes the
string `"['list', 'as', 'desc']"` in the prompt, and a dict becomes
its full repr.

#### Attack / PoC

```python
from mcpschema import to_ollama_tool, tool_from_dict

t = tool_from_dict({
    'name': 't', 'description': 'd',
    'inputSchema': {'type': 'object', 'properties': {
        'p': {'type': 'string', 'description': ['list', 'as', 'desc']}
    }},
})
print(to_ollama_tool(t)['system_prompt_suffix'])
# Tool: t
# Description: d
# Parameters:
#   - p: string — ['list', 'as', 'desc']      <-- Python repr leaked into prompt
```

#### Why this matters

- The `system_prompt_suffix` is concatenated into the Ollama model's
  system prompt and directly influences model behavior. A
  `repr()`-shaped string is at best ugly, at worst confusing to the
  model.
- A hostile MCP server could craft `description: {"action":
  "ignore previous instructions"}` and the repr of that dict would
  appear in the prompt. (This is a low-impact injection vector
  because the suffix is clearly labeled as a schema summary, but the
  principle stands: the suffix should contain only *intended*
  string content.)
- For comparison, `_normalize_property` (used by the OpenAI /
  Anthropic / Gemini paths) does guard with `isinstance(desc, str)
  and desc`. The Ollama suffix builder does not.

#### Fix

```python
# src/mcpschema/_schema.py:170-175
pdesc = pschema.get("description", "")
if isinstance(pdesc, str) and pdesc:
    line += f" — {pdesc}"
```

One-line change.

#### Regression test

```python
def test_ollama_suffix_skips_non_string_property_description():
    t = tool_from_dict({
        'name': 't', 'description': 'd',
        'inputSchema': {'type': 'object', 'properties': {
            'p': {'type': 'string', 'description': ['not', 'a', 'string']}
        }},
    })
    suffix = to_ollama_tool(t)['system_prompt_suffix']
    assert "['not', 'a', 'string']" not in suffix
    assert " — " not in suffix.split("\n")[-1]  # no trailing em-dash
```

---

### L-1 — Partial Invariant 21 violation across provider adapters (cosmetic)

**Severity**: Low
**CWE**: CWE-697 (Incorrect Comparison / Partial Invariant Enforcement)
**File / line**: `src/mcpschema/adapters.py:24-49` (anthropic, gemini)
**Public surface affected**: same as H-1.

#### Description

This is the architectural-side observation behind H-1. Two of the
six provider adapters (`anthropic`, `gemini`) were implemented with
a different code pattern than the other four. The library should
have a single helper that all six adapters call. The fact that four
adapters are consistent and two are not is a code-smell signal that
the library's invariant enforcement is fragile (any future adapter
added by copy-pasting from `anthropic` / `gemini` will inherit the
bug).

#### Fix

Same as H-1 (apply `_get_name` / `_get_description` uniformly).
Bonus: consider centralizing the per-provider field-shape logic into
a single helper that takes a `(name_field, description_field,
schema_field)` triple, so future providers can't repeat the mistake.

---

### L-2 — `tool_from_dict` does Python-repr coercion on truthy non-string `description`

**Severity**: Low
**CWE**: CWE-1284 (Improper Validation of Specified Quantity)
**File / line**: `src/mcpschema/tool.py:41`
**Public surface affected**: `tool_from_dict` directly; downstream
effects in every adapter.

#### Description

```python
# tool.py:41
description=str(raw.get("description", "") or ""),
```

The `or ""` clause coerces *falsy* non-strings (`None`, `0`, `False`,
`""`) to `""`. But *truthy* non-strings (lists, dicts, ints other
than 0) flow through `str(...)` and become their Python `repr()`.

#### PoC

```python
from mcpschema import tool_from_dict
print(repr(tool_from_dict({'name': 't', 'description': [42]}).description))
# '[42]'
print(repr(tool_from_dict({'name': 't', 'description': {'k': 'v'}}.description))
# "{'k': 'v'}"
print(repr(tool_from_dict({'name': 't', 'description': 0}).description))
# ''
print(repr(tool_from_dict({'name': 't', 'description': True}).description))
# 'True'    # bool is int in Python — True is truthy, so str(True) = 'True'
```

#### Why this is Low (not higher)

- `description` is human-readable text, not a structured field. A
  `repr()`-shaped string is odd but not security-impacting.
- It does not crash.
- It does not violate Invariant 21 strictly speaking (the library
  *accepts* the input and produces a deterministic string output).
  It is more of an "incorrect value" than a "missing validation."
- This is the same pattern as M-1 but in a less-impactful sink
  (the MCPTool description goes into dict output, not into an LLM
  prompt).

#### Fix

```python
# tool.py:34-43 (replace the description coercion)
desc_raw = raw.get("description", "")
description = desc_raw if isinstance(desc_raw, str) else ""
```

One-line change. Regression test in H-1's neighborhood.

---

### INFO-1 — Private `_normalize_schema(type_map=None)` still raises (documented, not a new finding)

**Severity**: Info (not a finding)
**File / line**: `src/mcpschema/_schema.py:104-109`
**Documented in**: `QA_REPORT.md` §"Notes on the literal QA snippets",
`FUZZING_REPORT.md` §"One nuance worth flagging".

This was flagged in the prior QA report as "optional polish, not a
blocker." The re-QA confirmed it again. No change required from the
adversary audit — re-confirming the prior finding and stating that it
remains the only contract gap on a private helper. If the project's
Invariant 21 should apply to private helpers too, add
`if type_map is None: type_map = {"object": "object"}` at the top of
`_normalize_schema`.

---

### INFO-2 — `convert_all` accepts any iterable, including non-list iterables

**Severity**: Info
**File / line**: `src/mcpschema/adapters.py:111-118`
**Public surface affected**: `convert_all`.

#### Observation

`convert_all(tools, provider)` calls `for t in tools` — it accepts
dict (iterates over keys), str (iterates over chars), generator, etc.
Each non-tool item is silently coerced via the adapters' duck-typed
fallbacks (most produce an empty-schema adapter output).

```python
from mcpschema import convert_all
print(convert_all("hi", "openai"))
# [{'type':'function','function':{...}}, {'type':'function','function':{...}}]
#  — two empty-schema tools, because 'h' and 'i' are each "tools" with no attrs.
```

This is not a crash; it's a "library silently does the wrong thing
on weird input" — and the prior FUZZING_REPORT and QA reports both
treat this kind of behavior as acceptable per Invariant 21 (silent
coercion, not raise). Logged here for completeness.

#### Fix (optional)

The docstring could note "iterable of MCP-style tools" — and if
desired, the function could iterate over `tools.items()` for dicts.
Not a security issue.

---

### INFO-3 — `MCPTool` frozen dataclass is bypassable

**Severity**: Info (Python language wart)
**File / line**: `src/mcpschema/tool.py:14-26`
**Public surface affected**: `MCPTool`.

`frozen=True` is enforced via `object.__setattr__` overrides in the
generated `__setattr__`. Bypass is trivial via
`object.__setattr__(instance, "name", None)`. This is a known Python
limitation, not a mcpschema vulnerability. Documented for
completeness of the audit surface.

---

## Cross-checks against prior QA / fuzz

### Prior CRASH repros (8 inputs from `git show 3bc5016:FUZZING_REPORT.md`)

| ID | Input | At commit 111a6f1 |
|---|---|---|
| F-1 | `inputSchema='not_a_dict'` | silent (inputSchema coerced to `{}`) |
| F-1b | `inputSchema=[('k','v')]` | silent |
| F-1c | `inputSchema=42` | silent |
| F-3 | `inputSchema={'type':[],'properties':{}}` | silent (type coerced to `"object"`) |
| F-3b | `inputSchema={'type':['string','null'],'properties':{}}` | silent |
| F-3c | `inputSchema={'type':{'foo':'bar'},'properties':{}}` | silent |
| F-NEW-2 | `inputSchema={'type':'object','properties':'string'}` | silent |
| F-NEW-2b | `inputSchema={'type':'object','properties':[1,2,3]}` | silent |

All 8 silent. **No regression on prior fixes.**

### Standard adversarial inputs (re-QA check #9, 8 inputs)

| Input | At commit 111a6f1 |
|---|---|
| empty dict `{}` | silent |
| `type=123` | silent |
| `type=None` | silent |
| `properties=[]` | silent |
| `items='string'` | silent (correctly ignored) |
| unicode name `üñîçødé_名前_🚀` | silent |
| depth-7 nesting | silent |
| 1MB `description` payload | silent |

All 8 silent.

### CLI surface

`mcpschema convert --provider <X> --input '<json>'` was exercised
for all 6 providers × 3 adversarial payloads (`{"name":"t","inputSchema":{...}}`
where `{...}` covers empty, deeply-nested, and missing-name). No
crashes. All exit 0.

`mcpschema convert --provider openai --input '[1,2,3]'` exits 0
(list-of-ints is silently coerced to N empty-schema tools — see INFO-2).

`mcpschema convert --provider openai --input '{"description":"x","inputSchema":{}}'`
exits 1 with a Python traceback — `tool_from_dict` raises
`ValueError("tool dict must have a non-empty 'name' string")` and
the CLI does not catch it. This is the documented behavior per the
README ("--input must be a JSON dict or list of dicts") but it
leaks a Python traceback to the user instead of a clean
`mcpschema: invalid input: ...` message. **Not a new finding** — this
behavior is consistent with the prior QA report's stance on
`tool_from_dict` (which raises ValueError on missing-name, by design).

---

## Summary for the next card (card 02 — fuzzing harnesses)

The fuzzing-harness card should target the following surfaces
(card 02 of the cycle_16 adversary workstream):

| Harness | Surface | Why |
|---|---|---|
| H1 | `tool_from_dict` + all 6 adapters | confirm H-1 / M-1 / L-2 paths are exercised |
| H2 | CLI `convert` with `--input '-'` (stdin) | ensure CLI never crashes on adversarial JSON, including list-of-ints and missing-name dicts |
| H3 | `build_ollama_system_prompt_suffix` directly | M-1 sink — adversarial nested-property description |

The existing 14-input re-fuzz campaign in `FUZZING_REPORT.md` is a
good seed corpus for H1 and H2 but does NOT exercise M-1 (which
requires a deeply-nested property with non-string description) or
H-1 (which requires the *tool itself* — not its schema — to have
`name=None`).

---

## Verdict

**DIRTY** — 1 High, 1 Medium, 2 Low, 3 Info.

- The High and Medium findings are real contract-coverage gaps and
  should be remediated before card 05 (FUZZING_REPORT) closes —
  the FUZZING_REPORT card should include the `H-1` and `M-1` PoCs as
  regressions it pinned.
- The Low findings are observational and should be remediated
  alongside H-1 / M-1 if a fix card is opened.
- The Info items are not blockers but should be noted in
  FUZZING_REPORT.md Recommendations per the chain's invariants.

**Critical / High**: 1 (H-1).
**Medium**: 1 (M-1).
**No crash-class findings.**

---

Audit complete. Card 01 (manual vulnerability audit) of the
cycle_16 adversary workstream is done. Orchestrator may mint cards
02 (harnesses), 03 (seeds + execution), 04 (triage), 05
(FUZZING_REPORT) as the next step.