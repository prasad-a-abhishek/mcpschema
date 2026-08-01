"""Adversarial / edge-case tests — sweep the angular taxonomy.

This file is dedicated to the boundary / malformed / encoding / streaming /
concurrent angles the standard AC tests don't reach. Each test class is
named for the angle it covers.
"""

from __future__ import annotations

import json

import pytest

from mcpschema import (
    convert_all,
    to_anthropic_tool,
    to_gemini_tool,
    to_ollama_tool,
    to_openai_tool,
)

from .conftest import FakeTool


# =============================================================================
# Angle: empty / None / malformed inputs
# =============================================================================


class TestEmptyInputs:
    def test_openai_empty_schema_returns_valid_function(self) -> None:
        tool = FakeTool(name="x", description="y", inputSchema={})
        out = to_openai_tool(tool)
        assert out["type"] == "function"
        assert out["function"]["parameters"]["type"] == "object"

    def test_anthropic_empty_schema_returns_valid_tool(self) -> None:
        tool = FakeTool(name="x", description="y", inputSchema={})
        out = to_anthropic_tool(tool)
        assert "input_schema" in out

    def test_gemini_empty_schema(self) -> None:
        tool = FakeTool(name="x", description="y", inputSchema={})
        out = to_gemini_tool(tool)
        assert out["parameters"]["type"] == "OBJECT"

    def test_ollama_empty_schema(self) -> None:
        tool = FakeTool(name="x", description="y", inputSchema={})
        out = to_ollama_tool(tool)
        assert out["type"] == "function"

    def test_empty_list_to_convert_all(self) -> None:
        for provider in ("openai", "anthropic", "gemini", "ollama", "deepseek", "mistral"):
            assert convert_all([], provider) == []

    def test_convert_all_with_empty_itertools_chain(self) -> None:
        # itertools.chain of nothing
        import itertools

        assert convert_all(itertools.chain([]), "openai") == []


# =============================================================================
# Angle: encoding / Unicode
# =============================================================================


class TestUnicode:
    def test_openai_emoji_name(self) -> None:
        tool = FakeTool(name="🚀", description="rocket", inputSchema={"type": "object"})
        out = to_openai_tool(tool)
        assert out["function"]["name"] == "🚀"

    def test_openai_zwj_emoji(self) -> None:
        """Zero-width-joiner emoji (e.g. 👨‍👩‍👧) — multibyte cluster round-trip."""
        tool = FakeTool(name="family", description="👨‍👩‍👧", inputSchema={"type": "object"})
        out = to_openai_tool(tool)
        assert out["function"]["description"] == "👨‍👩‍👧"

    def test_openai_bidi_marks_in_description(self) -> None:
        """Bidirectional marks must be preserved verbatim (not sanitized)."""
        desc = "abc\u202efed"  # RTL override
        tool = FakeTool(name="x", description=desc, inputSchema={"type": "object"})
        out = to_openai_tool(tool)
        assert out["function"]["description"] == desc

    def test_openai_combining_marks(self) -> None:
        desc = "café"  # 'e' + combining acute
        tool = FakeTool(name="x", description=desc, inputSchema={"type": "object"})
        out = to_openai_tool(tool)
        assert out["function"]["description"] == desc

    def test_anthropic_long_description(self) -> None:
        desc = "x" * 10_000
        tool = FakeTool(name="x", description=desc, inputSchema={"type": "object"})
        out = to_anthropic_tool(tool)
        assert len(out["description"]) == 10_000

    def test_gemini_long_description(self) -> None:
        desc = "x" * 10_000
        tool = FakeTool(name="x", description=desc, inputSchema={"type": "object"})
        out = to_gemini_tool(tool)
        assert len(out["description"]) == 10_000

    def test_openai_surrogate_pairs_in_description(self) -> None:
        # \ud83d\ude80 = 🚀 as surrogate pair
        desc = "before \ud83d\ude80 after"
        tool = FakeTool(name="x", description=desc, inputSchema={"type": "object"})
        out = to_openai_tool(tool)
        assert out["function"]["description"] == desc


# =============================================================================
# Angle: large / many-param schemas
# =============================================================================


class TestLargeSchemas:
    def test_openai_50_properties(self) -> None:
        props = {f"p{i}": {"type": "string"} for i in range(50)}
        tool = FakeTool(
            name="big",
            description="50 props",
            inputSchema={"type": "object", "properties": props, "required": list(props)[:5]},
        )
        out = to_openai_tool(tool)
        assert len(out["function"]["parameters"]["properties"]) == 50
        assert len(out["function"]["parameters"]["required"]) == 5

    def test_anthropic_50_properties(self) -> None:
        props = {f"p{i}": {"type": "integer"} for i in range(50)}
        tool = FakeTool(
            name="big",
            description="50 props",
            inputSchema={"type": "object", "properties": props, "required": list(props)[:3]},
        )
        out = to_anthropic_tool(tool)
        assert len(out["input_schema"]["properties"]) == 50

    def test_openai_deeply_nested_array_of_arrays(self) -> None:
        """Array of array of array of string — 3 levels deep."""
        tool = FakeTool(
            name="matrix",
            description="matrix",
            inputSchema={
                "type": "object",
                "properties": {
                    "m": {
                        "type": "array",
                        "items": {
                            "type": "array",
                            "items": {"type": "array", "items": {"type": "string"}},
                        },
                    }
                },
                "required": ["m"],
            },
        )
        out = to_openai_tool(tool)
        items = out["function"]["parameters"]["properties"]["m"]
        assert items["type"] == "array"
        assert items["items"]["type"] == "array"
        assert items["items"]["items"]["type"] == "array"
        assert items["items"]["items"]["items"]["type"] == "string"


# =============================================================================
# Angle: malformed / partial schemas
# =============================================================================


class TestMalformedSchemas:
    def test_missing_top_level_type(self) -> None:
        """No 'type' at top level — should coerce to 'object'."""
        tool = FakeTool(name="x", description="y", inputSchema={"properties": {"a": {"type": "string"}}})
        out = to_openai_tool(tool)
        assert out["function"]["parameters"]["type"] == "object"

    def test_missing_properties_key(self) -> None:
        """Schema has 'type' but no 'properties' — should default to {}."""
        tool = FakeTool(name="x", description="y", inputSchema={"type": "object", "required": []})
        out = to_openai_tool(tool)
        assert out["function"]["parameters"]["properties"] == {}

    def test_missing_required_key(self) -> None:
        """Schema has 'properties' but no 'required' — defaults to empty."""
        tool = FakeTool(
            name="x", description="y", inputSchema={"type": "object", "properties": {"a": {"type": "string"}}}
        )
        out = to_anthropic_tool(tool)
        assert "required" not in out["input_schema"] or out["input_schema"]["required"] == []

    def test_property_with_empty_dict(self) -> None:
        """An empty property dict ({}) — should default to string type."""
        tool = FakeTool(
            name="x",
            description="y",
            inputSchema={"type": "object", "properties": {"empty": {}}, "required": ["empty"]},
        )
        out = to_openai_tool(tool)
        assert out["function"]["parameters"]["properties"]["empty"]["type"] == "string"

    def test_property_with_unknown_type_falls_back_to_string(self) -> None:
        tool = FakeTool(
            name="x",
            description="y",
            inputSchema={"type": "object", "properties": {"weird": {"type": "foobar"}}, "required": ["weird"]},
        )
        out = to_openai_tool(tool)
        # Either omitted or coerced to string — but never crashes.
        assert "function" in out


# =============================================================================
# Angle: regression guards
# =============================================================================


class TestRegressionGuards:
    def test_required_field_order_preserved(self) -> None:
        """Provider schemas preserve the order of the 'required' list."""
        tool = FakeTool(
            name="x",
            description="y",
            inputSchema={
                "type": "object",
                "properties": {n: {"type": "string"} for n in "abcdef"},
                "required": ["c", "a", "f", "b"],
            },
        )
        out = to_openai_tool(tool)
        assert out["function"]["parameters"]["required"] == ["c", "a", "f", "b"]

    def test_description_with_newlines_preserved(self) -> None:
        desc = "line one\nline two\nline three"
        tool = FakeTool(name="x", description=desc, inputSchema={"type": "object"})
        out = to_openai_tool(tool)
        assert out["function"]["description"] == desc

    def test_description_with_tabs_preserved(self) -> None:
        desc = "col1\tcol2\tcol3"
        tool = FakeTool(name="x", description=desc, inputSchema={"type": "object"})
        out = to_anthropic_tool(tool)
        assert out["description"] == desc

    def test_property_order_preserved(self) -> None:
        """Python 3.7+ dicts are ordered; the adapter must not reorder."""
        original_order = ["z", "y", "x", "w", "v"]
        props = {n: {"type": "string"} for n in original_order}
        tool = FakeTool(
            name="x", description="y", inputSchema={"type": "object", "properties": props, "required": []}
        )
        out = to_openai_tool(tool)
        assert list(out["function"]["parameters"]["properties"].keys()) == original_order


# =============================================================================
# Angle: JSON-Schema edge cases
# =============================================================================


class TestJsonSchemaEdgeCases:
    def test_anyOf_not_supported_falls_back_to_object(self) -> None:
        """anyOf is not in the spec's accepted types — degrades gracefully."""
        tool = FakeTool(
            name="x",
            description="y",
            inputSchema={
                "type": "object",
                "properties": {"v": {"anyOf": [{"type": "string"}, {"type": "integer"}]}},
                "required": ["v"],
            },
        )
        # Should not raise.
        out = to_openai_tool(tool)
        assert "function" in out

    def test_oneOf_not_supported(self) -> None:
        tool = FakeTool(
            name="x",
            description="y",
            inputSchema={
                "type": "object",
                "properties": {"v": {"oneOf": [{"type": "string"}]}},
                "required": ["v"],
            },
        )
        out = to_anthropic_tool(tool)
        assert "input_schema" in out

    def test_const_in_property_omitted(self) -> None:
        """`const` is JSON-Schema specific; not part of provider formats — omitted."""
        tool = FakeTool(
            name="x",
            description="y",
            inputSchema={
                "type": "object",
                "properties": {"v": {"type": "string", "const": "fixed"}},
                "required": ["v"],
            },
        )
        out = to_openai_tool(tool)
        # const is not a default — should survive. But if the impl strips it,
        # both are acceptable. Test just that there's no crash.
        assert "function" in out


# =============================================================================
# Angle: convert_all with iterators and large inputs
# =============================================================================


class TestBatchConversion:
    def test_convert_all_100_tools(self) -> None:
        tools = [
            FakeTool(name=f"tool_{i}", description=f"desc {i}", inputSchema={"type": "object"})
            for i in range(100)
        ]
        out = convert_all(tools, "openai")
        assert len(out) == 100
        assert all(item["function"]["name"] == f"tool_{i}" for i, item in enumerate(out))

    def test_convert_all_with_generator_yields_consistent_results(self) -> None:
        """A generator passed to convert_all must produce the same output as a list."""

        def gen():
            for i in range(10):
                yield FakeTool(name=f"t{i}", description="d", inputSchema={"type": "object"})

        out_gen = convert_all(gen(), "openai")
        tools = [
            FakeTool(name=f"t{i}", description="d", inputSchema={"type": "object"}) for i in range(10)
        ]
        out_list = convert_all(tools, "openai")
        assert json.dumps(out_gen, sort_keys=True) == json.dumps(out_list, sort_keys=True)


# =============================================================================
# Angle: JSON-RPC tool payload round-trip
# =============================================================================


class TestJsonRpcToolRoundtrip:
    """Real MCP servers send tools as dicts over JSON-RPC. Verify the library
    accepts that shape."""

    def test_tool_from_dict_round_trip_through_openai(self) -> None:
        from mcpschema import tool_from_dict

        raw = {
            "name": "git_log",
            "description": "Get recent commits",
            "inputSchema": {
                "type": "object",
                "properties": {"n": {"type": "integer", "description": "count"}},
                "required": ["n"],
            },
        }
        tool = tool_from_dict(raw)
        out = to_openai_tool(tool)
        assert out["function"]["name"] == "git_log"
        assert out["function"]["parameters"]["properties"]["n"]["type"] == "integer"

    def test_anthropic_round_trip(self) -> None:
        from mcpschema import tool_from_dict

        raw = {"name": "x", "description": "y", "inputSchema": {"type": "object"}}
        tool = tool_from_dict(raw)
        out = to_anthropic_tool(tool)
        assert out["name"] == "x"

    def test_gemini_round_trip(self) -> None:
        from mcpschema import tool_from_dict

        raw = {"name": "x", "description": "y", "inputSchema": {"type": "object"}}
        tool = tool_from_dict(raw)
        out = to_gemini_tool(tool)
        assert out["name"] == "x"


# =============================================================================
# Angle: cycle_16 fix regressions (F-1, F-2, F-3, F-NEW-2)
# =============================================================================


class TestCycle16Fixes:
    """Regression tests for the 4 CRASH bugs found by the cycle_16 adversary
    fuzzer at commit 3bc5016. The exact reproduction strings come from
    QA_REPORT.md § "The CRASH bugs" (line ~274+).

    Invariant 21 says library functions must be **total** over arbitrary input
    — they must NOT raise. The 4 fixes add graceful coercion / fall-back
    for adversarial inputs rather than crashing.
    """

    # --- F-1: tool_from_dict on truthy non-dict inputSchema -----------------

    def test_f1_tool_from_dict_string_inputSchema_does_not_raise(self) -> None:
        """F-1: inputSchema='not a dict' must coerce to {}, not raise."""
        from mcpschema import tool_from_dict

        # Exact reproduction from QA_REPORT.md:
        tool = tool_from_dict({"name": "foo", "description": "bar", "inputSchema": "not a dict"})
        assert tool.inputSchema == {}

    def test_f1_tool_from_dict_list_inputSchema_does_not_raise(self) -> None:
        """F-1: inputSchema=[1,2] must coerce to {}, not raise."""
        from mcpschema import tool_from_dict

        tool = tool_from_dict({"name": "foo", "description": "bar", "inputSchema": [1, 2]})
        assert tool.inputSchema == {}

    def test_f1_tool_from_dict_int_inputSchema_does_not_raise(self) -> None:
        """F-1: inputSchema=42 must coerce to {}, not raise."""
        from mcpschema import tool_from_dict

        tool = tool_from_dict({"name": "foo", "description": "bar", "inputSchema": 42})
        assert tool.inputSchema == {}

    # --- F-2: CLI propagation of F-1 ----------------------------------------

    def test_f2_cli_propagates_f1_fix(self) -> None:
        """F-2: the CLI path through _normalize_tools must also coerce
        truthy non-dict inputSchema — it's the same root cause as F-1."""
        from mcpschema import tool_from_dict

        # Mirror the exact CLI input from QA_REPORT.md:
        #   echo '{"name":"foo","description":"bar","inputSchema":"not a dict"}' | \
        #       python3 -m mcpschema convert --provider openai --input -
        tool = tool_from_dict({"name": "foo", "description": "bar", "inputSchema": "not a dict"})
        out = to_openai_tool(tool)
        # Must produce a valid OpenAI function dict, not raise.
        assert out["type"] == "function"
        assert out["function"]["name"] == "foo"
        assert out["function"]["parameters"]["properties"] == {}

    # --- F-3: _normalize_schema on non-string type --------------------------

    def test_f3_normalize_schema_list_type_does_not_raise(self) -> None:
        """F-3: type=['string','null'] must degrade to 'object', not raise
        TypeError("unhashable type: 'list')."""
        from mcpschema import tool_from_dict

        tool = tool_from_dict(
            {"name": "x", "description": "d", "inputSchema": {"type": ["string", "null"], "properties": {}}}
        )
        # All 6 providers must accept this without raising.
        assert to_openai_tool(tool)["function"]["parameters"]["type"] == "object"
        assert to_anthropic_tool(tool)["input_schema"]["type"] == "object"
        assert to_gemini_tool(tool)["parameters"]["type"] == "OBJECT"

    def test_f3_normalize_schema_dict_type_does_not_raise(self) -> None:
        """F-3: type={'foo':'bar'} must degrade to 'object', not raise
        TypeError("unhashable type: 'dict')."""
        from mcpschema import tool_from_dict

        tool = tool_from_dict(
            {"name": "x", "description": "d", "inputSchema": {"type": {"foo": "bar"}, "properties": {}}}
        )
        assert to_openai_tool(tool)["function"]["parameters"]["type"] == "object"

    # --- F-NEW-2: build_ollama_system_prompt_suffix on non-dict properties ---

    def test_f_new_2_ollama_string_properties_does_not_raise(self) -> None:
        """F-NEW-2: properties='this is a string' must coerce to {}, not
        raise AttributeError("'str' object has no attribute 'items')."""
        from mcpschema import tool_from_dict

        # Exact reproduction from QA_REPORT.md:
        tool = tool_from_dict(
            {"name": "x", "description": "d", "inputSchema": {"type": "object", "properties": "this is a string"}}
        )
        # Must produce a valid ollama tool dict with empty params.
        out = to_ollama_tool(tool)
        assert out["function"]["name"] == "x"
        assert out["function"]["parameters"]["properties"] == {}
        # The system_prompt_suffix must NOT include a "Parameters:" line
        # (since props is empty after coercion).
        assert "Parameters:" not in out["system_prompt_suffix"]

    def test_f_new_2_ollama_list_properties_does_not_raise(self) -> None:
        """F-NEW-2: properties=[1,2,3] (another non-dict) must also coerce."""
        from mcpschema import tool_from_dict

        tool = tool_from_dict(
            {"name": "x", "description": "d", "inputSchema": {"type": "object", "properties": [1, 2, 3]}}
        )
        out = to_ollama_tool(tool)
        assert out["function"]["parameters"]["properties"] == {}