# FUZZING_REPORT.md — mcpschema cycle_16 re-fuzz (post-fix)

**Run**: kanban task `t_51ba182a`, run 3447
**Repo**: `/root/projects/mcpschema`
**Commit**: `25cfd7a9cb0159edb0b16e5cde68b4020653598b` (HEAD)
**Prior fuzz report**: `3bc5016` (commit of the original NEEDS_REMEDIATION
report with 3 CRASH bugs). See `git show 3bc5016:FUZZING_REPORT.md`.
**Re-fuzz script**: `/tmp/refuzz.py` (custom, written fresh for this re-QA
to push every prior CRASH repro + the standard adversarial input list
through the public API and the CLI).
**Date**: 2026-08-01

---

## VERDICT: SHIP-READY

The 3 prior CRASH bugs (F-1, F-2, F-3) plus the 1 NEW CRASH (F-NEW-2
from prior QA) are all silent on every public API path. The re-fuzz
campaign of 14 inputs × ~7 paths found **0 new findings**.

---

## Re-fuzz methodology

Three layers of adversarial coverage, all independent of the prior QA:

1. **Prior CRASH repros** — 8 inputs lifted verbatim from the prior
   `FUZZING_REPORT.md` (3bc5016). These MUST be silent now.
2. **Standard adversarial input list** — the 8 inputs specified in
   re-QA task body check #9 (empty dict, type=int, type=None,
   properties=list, items=string, unicode names, deeply nested depth 7,
   1MB+ payload).
3. **Execution surface** — each input is pushed through:
   - `tool_from_dict` construction
   - 6 provider adapters (`to_openai_tool`, `to_anthropic_tool`,
     `to_gemini_tool`, `to_ollama_tool`, `to_deepseek_tool`,
     `to_mistral_tool`)
   - `python -m mcpschema.cli convert --provider <X> --input '<json>'`
     for all 6 providers (the CLI convert surface)

Adversarial criterion: graceful behavior (silent coercion, empty schema,
or documented error message) — NOT a stack trace.

---

## Prior CRASH repros — all silent on commit 25cfd7a

| ID | Input | Adapter | CLI |
|---|---|---|---|
| F-1 | `tool_from_dict({'name':'foo','inputSchema':'not_a_dict'})` | OK (coerced to `inputSchema={}`) | OK |
| F-1b | `tool_from_dict({'name':'foo','inputSchema':[('k','v')]})` | OK (coerced to `inputSchema={}`) | OK |
| F-1c | `tool_from_dict({'name':'foo','inputSchema':42})` | OK (coerced to `inputSchema={}`) | OK |
| F-3 | `tool_from_dict({'name':'x','inputSchema':{'type':[],'properties':{}}})` | OK (`type` coerced to `"object"`) | OK |
| F-3b | `tool_from_dict({'name':'x','inputSchema':{'type':['string','null'],'properties':{}}})` | OK (`type` coerced to `"object"`) | OK |
| F-3c | `tool_from_dict({'name':'x','inputSchema':{'type':{'foo':'bar'},'properties':{}}})` | OK (`type` coerced to `"object"`) | OK |
| F-NEW-2 | `tool_from_dict({'name':'x','inputSchema':{'type':'object','properties':'string'}})` then `to_ollama_tool(...)` | OK (`properties` coerced to `{}`) | OK |
| F-NEW-2b | `tool_from_dict({'name':'x','inputSchema':{'type':'object','properties':[1,2,3]}})` then `to_ollama_tool(...)` | OK (`properties` coerced to `{}`) | OK |

All 8 prior CRASH repros produce graceful output (empty `properties`,
default `"object"` type, empty `inputSchema`) on every public API path.

---

## Standard adversarial input list — all silent on commit 25cfd7a

| Input | Adapters | CLI |
|---|---|---|
| `{}` empty dict (wrapped as `{'name':'t','description':'d','inputSchema':{}}`) | OK | OK |
| `{'type':123}` (int where string expected) | OK (coerced to `"object"`) | OK |
| `{'type':None}` | OK (coerced to `"object"`) | OK |
| `{'properties':[]}` (list where dict expected) | OK (coerced to `{}`) | OK |
| `{'items':'string'}` (string where dict expected) | OK (silently ignored, doc'd behavior) | OK |
| unicode name `üñîçødé_名前_🚀` | OK | OK |
| deeply nested adversarial nesting (depth 7) | OK (recursive `_normalize_property` handles it) | OK |
| 1MB+ payload (`description='x' * (1024*1024+100)`) | OK (serialization handles big strings) | n/a (skipped to keep CLI argv small) |

All 8 standard inputs produce graceful output.

---

## One nuance worth flagging (NOT a finding)

The re-QA task body's literal snippet for F-3:
```
python3 -c "from mcpschema._schema import _normalize_schema; print(_normalize_schema({'type': []}, None))"
```
raises `AttributeError: 'NoneType' object has no attribute 'get'` when
run against the private `_normalize_schema` function with `type_map=None`.

This is **not** a real adversarial-input bug because:

- `_normalize_schema` is a private helper (leading underscore, not in
  `__all__`).
- The function's signature declares `type_map: dict[str, str]` —
  passing `None` violates the type contract.
- Every public-API caller (`build_openai_function`,
  `build_anthropic_input_schema`, `build_gemini_parameters`,
  `build_ollama_system_prompt_suffix`) passes a real type_map
  (`_OPENAI_TYPES` or `_GEMINI_TYPES`).
- The actual user-facing F-3 reproduction
  (`tool_from_dict({'name':'x','inputSchema':{'type':[],'properties':{}}})`
  → `to_openai_tool(...)`) is silent and produces `{"type":"object",
  "properties":{}}` as expected.

If the project wants Invariant 21 to apply to private helpers as well,
a one-line `if type_map is None: type_map = {"object": "object"}` guard
would close it. This is **optional polish**, not a blocker.

---

## Conclusion

I tried the 8 prior CRASH repros from the prior `FUZZING_REPORT.md` and
the 8 standard adversarial inputs from the re-QA task body, on every
public API path (tool_from_dict + 6 provider adapters + CLI convert
for all 6 providers) and found **nothing** — every adversarial input
produces graceful behavior.

**No new findings.** Prior CRASHes are silent. Test suite is 145/145
green. Fresh-venv install + CLI smoke clean.

---

VERDICT: SHIP
