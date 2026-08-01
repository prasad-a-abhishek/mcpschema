#!/usr/bin/env python3
"""Adversarial fuzzer for mcpschema — 5000+ mutations across all surfaces."""

import sys
import random
import string
import traceback
from io import StringIO
from typing import Any

# Ensure we use the local package
sys.path.insert(0, "/root/projects/mcpschema/src")

from mcpschema import (
    to_openai_tool, to_anthropic_tool, to_gemini_tool,
    to_ollama_tool, to_deepseek_tool, to_mistral_tool,
    convert, convert_all, tool_from_dict, MCPTool,
    PROVIDERS,
)
from mcpschema._schema import (
    _normalize_property, _normalize_schema,
    _get_schema, _get_name, _get_description,
    build_openai_function, build_anthropic_input_schema,
    build_gemini_parameters, build_ollama_system_prompt_suffix,
    _OPENAI_TYPES, _GEMINI_TYPES,
)


# ── Mutation generators ──────────────────────────────────────────────────────

def mutate_str(s: str) -> str:
    """Apply random string mutations."""
    ops = [
        lambda x: x + "\x00",          # null byte
        lambda x: x + "\n",            # newline
        lambda x: x + "\r",            # carriage return
        lambda x: x + "\x1b",          # ANSI escape
        lambda x: x + " " * 1000,      # huge whitespace
        lambda x: x * 100,             # repetition
        lambda x: "\ufeff" + x,        # BOM
        lambda x: x.translate({i: '?' for i in range(32)}),  # strip control chars
        lambda x: x + "".join(random.choices(string.printable, k=500)),  # random noise suffix
        lambda x: "",                   # empty
    ]
    return random.choice(ops)(s)


def make_fuzz_tool() -> dict[str, Any]:
    """Generate a random fuzz tool dict."""
    n_props = random.randint(0, 5)
    props = {}
    for _ in range(n_props):
        pname = random.choice([
            "foo", "bar", "baz",
            mutate_str("x" * 10),
            mutate_str(""),
            mutate_str("a" * 1000),
        ])
        ptypes = ["string", "integer", "number", "boolean", "array", "object", "null", None, 123, [], {}]
        props[pname] = {
            "type": random.choice(ptypes),
            "description": mutate_str("desc"),
            "default": random.choice([None, 1, "x", [], {}]),
        }
    return {
        "name": mutate_str(random.choice(["mytool", "x", "", "a" * 1000, "tool\x00name"])),
        "description": mutate_str(random.choice(["", "A useful tool", "x" * 10000, "\n\t\x1b"])),
        "inputSchema": {
            "type": random.choice(["object", None, "", 123, [], {}]),
            "properties": props if random.random() > 0.2 else mutate_str("bad"),
            "required": random.choice([[], ["a", "b"], [1, 2], [None], ""]),
        },
    }


def make_fuzz_tool_non_dict() -> Any:
    """Return non-dict values to test duck-typing."""
    return random.choice([
        None,
        42,
        "string",
        [],
        {},
        {"name": None},
        {"name": 123},
        {"name": ""},
        {"name": []},
        {"name": {"nested": "dict"}},
        set(),
        object(),
    ])


# ── Surface (a): Core library ────────────────────────────────────────────────

def fuzz_core() -> list[tuple[str, Exception]]:
    """Fuzz all public adapter functions + helpers."""
    findings = []
    TOOLS = [make_fuzz_tool() for _ in range(200)]
    PROVIDER_FNS = {
        "openai": to_openai_tool,
        "anthropic": to_anthropic_tool,
        "gemini": to_gemini_tool,
        "ollama": to_ollama_tool,
        "deepseek": to_deepseek_tool,
        "mistral": to_mistral_tool,
    }

    for i, raw_tool in enumerate(TOOLS):
        # Pass raw dict
        for prov_name, fn in PROVIDER_FNS.items():
            try:
                result = fn(raw_tool)
                assert isinstance(result, dict), f"{prov_name} returned non-dict: {type(result)}"
            except Exception as e:
                findings.append((f"core/{prov_name}/dict", e))

        # Pass MCPTool
        try:
            tool = tool_from_dict(raw_tool)
            for prov_name, fn in PROVIDER_FNS.items():
                try:
                    result = fn(tool)
                except Exception as e:
                    findings.append((f"core/{prov_name}/MCPTool", e))
        except Exception as e:
            findings.append(("core/tool_from_dict", e))

        # Pass non-dict
        nd = make_fuzz_tool_non_dict()
        for prov_name, fn in PROVIDER_FNS.items():
            try:
                fn(nd)
            except Exception as e:
                findings.append((f"core/{prov_name}/non_dict:{type(nd).__name__}", e))

    # Fuzz convert/convert_all
    for i in range(100):
        tools = [make_fuzz_tool() for _ in range(random.randint(1, 10))]
        for prov in PROVIDERS:
            try:
                r = convert_all(tools, prov)
                assert isinstance(r, list)
            except Exception as e:
                findings.append((f"core/convert_all/{prov}", e))
            try:
                r = convert(tools[0], prov)
                assert isinstance(r, dict)
            except Exception as e:
                findings.append((f"core/convert/{prov}", e))

    # Fuzz invalid provider
    for i in range(50):
        bad_name = mutate_str(random.choice(["openai", "gemini", "xyz"]))
        if bad_name.lower() not in PROVIDERS:
            try:
                convert(TOOLS[0], bad_name)
            except ValueError:
                pass  # expected
            except Exception as e:
                findings.append((f"core/convert/bad_provider:{bad_name!r}", e))

    # Fuzz _normalize_property with extreme inputs
    extreme_props = [
        None, 42, [], {}, "string",
        {"type": None}, {"type": []}, {"type": {}},
        {"type": "string", "description": None},
        {"type": "string", "items": "bad"},
        {"type": "string", "items": []},
        {"type": "string", "items": 123},
        {"type": "string", "properties": "bad"},
        {"type": "string", "properties": []},
        {"type": "string", "properties": 123},
        {"type": "string", "enum": "bad"},
        {"type": "string", "enum": [1, 2, 3]},
        {"type": "string", "enum": [None, 1, "x"]},
        {"type": "string", "required": "bad"},
        {"type": "string", "required": [1, 2]},
        {"type": "string", "required": [None]},
    ]
    for prop in extreme_props:
        for type_map in [_OPENAI_TYPES, _GEMINI_TYPES]:
            try:
                _normalize_property(prop, type_map)
            except Exception as e:
                findings.append((f"core/_normalize_property/{type(prop).__name__}/{type_map is _GEMINI_TYPES}", e))

    # Fuzz _normalize_schema with extreme inputs
    extreme_schemas = [
        None, 42, "string", [], set(),
        {}, {"type": None}, {"type": []}, {"type": {}},
        {"properties": "bad"}, {"properties": []}, {"properties": 123},
        {"required": "bad"}, {"required": [1, 2]}, {"required": [None]},
        {"type": "object", "properties": None},
        {"type": "object", "properties": {"a": "not_a_dict"}},
        {"type": "object", "properties": {"a": None}},
    ]
    for schema in extreme_schemas:
        for type_map in [_OPENAI_TYPES, _GEMINI_TYPES]:
            try:
                _normalize_schema(schema, type_map)
            except Exception as e:
                findings.append((f"core/_normalize_schema/{type(schema).__name__}", e))

    # Fuzz build_* functions
    for _ in range(200):
        t = random.choice([make_fuzz_tool(), make_fuzz_tool_non_dict()])
        for fn_name in ["build_openai_function", "build_anthropic_input_schema",
                        "build_gemini_parameters", "build_ollama_system_prompt_suffix"]:
            try:
                {"build_openai_function": build_openai_function,
                 "build_anthropic_input_schema": build_anthropic_input_schema,
                 "build_gemini_parameters": build_gemini_parameters,
                 "build_ollama_system_prompt_suffix": build_ollama_system_prompt_suffix}[fn_name](t)
            except Exception as e:
                findings.append((f"core/{fn_name}", e))

    return findings


# ── Surface (b): CLI ─────────────────────────────────────────────────────────

def fuzz_cli() -> list[tuple[str, Exception]]:
    """Fuzz the CLI entrypoint."""
    from mcpschema.cli import main, _build_parser, _read_input, _normalize_tools
    findings = []

    # Generate fuzzed argv combos
    good_inputs = [
        '[{"name":"t","description":"d","inputSchema":{"type":"object","properties":{"x":{"type":"string"}}}}]',
        '{"name":"t","description":"d","inputSchema":{}}',
        '[{"name":"t1"},{"name":"t2"}]',
    ]
    fuzzed_inputs = [mutate_str(inp) for inp in good_inputs]

    # Valid argv combos
    valid_combos = []
    for provider in PROVIDERS:
        for inp in good_inputs:
            valid_combos.append(["mcpschema", "convert", "--provider", provider, "--input", inp])
            valid_combos.append(["mcpschema", "convert", "--provider", provider, "--input", "-"])

    for argv in valid_combos[:50]:
        try:
            # Redirect stdin if needed
            if "--input" in argv and argv[argv.index("--input")+1] == "-":
                old_stdin = sys.stdin
                sys.stdin = StringIO(random.choice(good_inputs))
                try:
                    main(argv)
                finally:
                    sys.stdin = old_stdin
            else:
                main(argv)
        except SystemExit as e:
            if e.code not in (0, 2):  # 2 = argparse error, acceptable
                findings.append((f"cli/valid_combo:{argv}", SystemExit(e.code)))
        except Exception as e:
            findings.append((f"cli/valid_combo:{argv}", e))

    # Invalid argv fuzzing
    bad_argv_templates = [
        ["mcpschema", "convert"],
        ["mcpschema", "convert", "--provider", "OPENAI"],
        ["mcpschema", "convert", "--provider", mutate_str("openai"), "--input", "{}"],
        ["mcpschema", "convert", "--provider", "openai"],
        ["mcpschema", "convert", "--input", "[{}]"],
        ["mcpschema", "convert", "--provider", "openai", "--input", mutate_str("[{}]")],
        ["mcpschema", "convert", "--provider", "openai", "--input", "not json at all"],
        ["mcpschema", "convert", "--provider", "openai", "--input", ""],
        ["mcpschema", "convert", "--provider", "openai", "--input", "null"],
        ["mcpschema", "convert", "--provider", "openai", "--input", "123"],
        ["mcpschema", "convert", "--provider", "openai", "--input", "true"],
        ["mcpschema"],
        ["mcpschema", "providers"],
        ["mcpschema", "--help"],
        ["mcpschema", "--version"],
        ["mcpschema", "convert", "--provider", "openai", "--compact"],
        ["mcpschema", "convert", "--provider", "openai", "--input", "[{}]", "--compact"],
        ["mcpschema", "unknown_cmd"],
        ["mcpschema", "convert", "--provider", "openai", "--input", '{"name": 1}'],  # name not str
        ["mcpschema", "convert", "--provider", "openai", "--input", '{"name": ""}'],  # name empty
        ["mcpschema", "convert", "--provider", "openai", "--input", '{"name": "x", "description": 123}'],
    ]

    for argv in bad_argv_templates:
        try:
            main(argv.copy())
        except SystemExit as e:
            if e.code not in (0, 2):
                findings.append((f"cli/bad_argv:{argv}", SystemExit(e.code)))
        except Exception as e:
            findings.append((f"cli/bad_argv:{argv}", e))

    # Fuzz _read_input
    read_inputs = [
        "[{}]", "[{\"name\":\"x\",\"description\":\"\",\"inputSchema\":{}}]",
        "null", "true", "false", "0", "1", '""', '"hello"',
        mutate_str("[{}]"), mutate_str("{}"), mutate_str(""),
    ]
    for v in read_inputs:
        try:
            _read_input(v)
        except SystemExit:
            pass
        except Exception as e:
            findings.append((f"cli/_read_input:{v!r}", e))

    # Fuzz _normalize_tools
    norm_inputs = [
        {}, [], None, 42, "string", {"name": "x"}, {"description": "d"},
        {"name": None}, {"name": ""}, {"name": 123},
        [{"name": "x"}, {"name": "y"}],
        [{"name": "x"}, 42, {"name": "z"}],  # mixed list with non-dict
        [{"name": "x"}, None],
    ]
    for v in norm_inputs:
        try:
            _normalize_tools(v)
        except SystemExit:
            pass
        except Exception as e:
            findings.append((f"cli/_normalize_tools:{v!r}", e))

    return findings


# ── Surface (c): Integration / chaining ─────────────────────────────────────

def fuzz_integration() -> list[tuple[str, Exception]]:
    """Fuzz chains of operations, round-trips, and large payloads."""
    findings = []

    # Very large tool schemas
    big_props = {f"prop_{i}": {"type": random.choice(["string","integer"]), "description": "x" * 200}
                 for i in range(200)}
    big_tool = {
        "name": "bigtool",
        "description": "x" * 1000,
        "inputSchema": {"type": "object", "properties": big_props, "required": list(big_props.keys())[:50]},
    }
    for prov in PROVIDERS:
        try:
            convert(big_tool, prov)
        except Exception as e:
            findings.append((f"integration/big_tool/{prov}", e))

    # Deeply nested properties
    def make_nested(depth: int) -> dict:
        if depth <= 0:
            return {"type": "string"}
        return {"type": "object", "properties": {"nested": make_nested(depth - 1)}}

    for depth in [5, 10, 20, 50]:
        t = {"name": "nested", "description": "", "inputSchema": {"type": "object", "properties": make_nested(depth)}}
        for prov in PROVIDERS:
            try:
                convert(t, prov)
            except Exception as e:
                findings.append((f"integration/nested_depth_{depth}/{prov}", e))

    # Empty inputSchema
    for inp in [{}, {"type": "object"}, {"properties": {}}, {"type": None}]:
        t = {"name": "t", "description": "d", "inputSchema": inp}
        for prov in PROVIDERS:
            try:
                r = convert(t, prov)
            except Exception as e:
                findings.append((f"integration/empty_schema/{prov}", e))

    # Edge: required with non-string keys
    t = {"name": "t", "inputSchema": {"type": "object", "properties": {"x": {"type": "string"}}, "required": [1, "a", None]}}
    for prov in PROVIDERS:
        try:
            convert(t, prov)
        except Exception as e:
            findings.append((f"integration/weird_required/{prov}", e))

    # Enum with mixed types
    t = {"name": "t", "inputSchema": {"type": "object", "properties": {"x": {"type": "string", "enum": [1, "a", None, []]}}}}
    for prov in PROVIDERS:
        try:
            convert(t, prov)
        except Exception as e:
            findings.append((f"integration/mixed_enum/{prov}", e))

    return findings


# ── Runner ───────────────────────────────────────────────────────────────────

def main():
    all_findings = []

    print("=== Surface (a): Core Library ===")
    findings_a = fuzz_core()
    all_findings.extend(findings_a)
    print(f"  {len(findings_a)} findings")

    print("=== Surface (b): CLI ===")
    findings_b = fuzz_cli()
    all_findings.extend(findings_b)
    print(f"  {len(findings_b)} findings")

    print("=== Surface (c): Integration ===")
    findings_c = fuzz_integration()
    all_findings.extend(findings_c)
    print(f"  {len(findings_c)} findings")

    print(f"\n=== SUMMARY: {len(all_findings)} total findings ===")

    if all_findings:
        # Group by type
        from collections import Counter
        type_counts: Counter[str] = Counter(k for k, _ in all_findings)
        print("\nBy surface/type:")
        for k, v in type_counts.most_common(20):
            print(f"  {k}: {v}")

        # Show first few unique exceptions
        seen: set[str] = set()
        for key, exc in all_findings[:30]:
            sig = f"{type(exc).__name__}:{exc}"
            if sig not in seen:
                seen.add(sig)
                print(f"\n  [{key}] {type(exc).__name__}: {exc}")
    else:
        print("\n✓ No unhandled exceptions — all mutations handled gracefully")

    return len(all_findings)


if __name__ == "__main__":
    sys.exit(main())
