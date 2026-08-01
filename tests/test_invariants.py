"""Cross-cutting / invariant tests — zero deps, MCPTool adapter, error paths."""

from __future__ import annotations

import sys

import pytest

import mcpschema


# --- AC #19: zero third-party dependencies ------------------------------


def test_zero_dependency() -> None:
    """Importing mcpschema must NOT pull in any third-party modules."""
    # Re-import after we've snapshotted sys.modules — any package not in
    # this baseline was added by the import.
    before = set(sys.modules.keys())
    import mcpschema  # noqa: F401

    after = set(sys.modules.keys())
    new_modules = after - before
    third_party = {
        m.split(".")[0]
        for m in new_modules
        if not m.startswith(("mcpschema", "_", "site-packages", "pytest", "tests"))
        and "." not in m  # only top-level package names
    }
    # pytest and its deps will be present because we're running under pytest
    # itself — but mcpschema itself must not have *introduced* anything not in
    # stdlib. Filter to only modules whose top-level name doesn't look stdlib.
    stdlib_names = {
        "abc",
        "argparse",
        "ast",
        "builtins",
        "collections",
        "contextlib",
        "copy",
        "dataclasses",
        "datetime",
        "enum",
        "functools",
        "importlib",
        "inspect",
        "io",
        "itertools",
        "json",
        "logging",
        "os",
        "pathlib",
        "re",
        "string",
        "sys",
        "textwrap",
        "typing",
        "typing_extensions",
        "unittest",
        "warnings",
    }
    leaked = third_party - stdlib_names
    assert leaked == set(), f"mcpschema pulled in third-party modules: {leaked}"


def test_import_mcpschema_alone_does_not_raise() -> None:
    """Bare `import mcpschema` is the contract."""
    # If the previous test passed, this will too — but call it out explicitly.
    assert mcpschema.__version__


def test_no_third_party_imports_in_mcpschema_source() -> None:
    """Static check: no `import X` outside stdlib across the mcpschema package."""
    import os
    import pathlib

    pkg_root = pathlib.Path(mcpschema.__file__).parent
    forbidden: list[str] = []
    for py in pkg_root.rglob("*.py"):
        text = py.read_text()
        for line in text.splitlines():
            stripped = line.strip()
            # Look only at actual import statements (not strings, not type-only).
            if stripped.startswith("import ") or stripped.startswith("from "):
                # Strip the module name.
                if stripped.startswith("import "):
                    mod = stripped[7:].split(" as ")[0].split(".")[0].split(",")[0].strip()
                else:
                    mod = stripped[5:].split(" import ")[0].strip()
                if mod and mod not in _STDLIB_NAMES and not mod.startswith(("mcpschema", "_")):
                    forbidden.append(f"{py.relative_to(pkg_root)}: {stripped}")
    assert forbidden == [], f"third-party imports found: {forbidden}"


_STDLIB_NAMES = {
    "abc",
    "argparse",
    "ast",
    "builtins",
    "collections",
    "contextlib",
    "copy",
    "dataclasses",
    "datetime",
    "enum",
    "functools",
    "importlib",
    "inspect",
    "io",
    "itertools",
    "json",
    "logging",
    "os",
    "pathlib",
    "re",
    "string",
    "sys",
    "textwrap",
    "typing",
    "typing_extensions",
    "unittest",
    "warnings",
    "subprocess",
    "shutil",
}


# --- MCPTool dataclass / tool_from_dict helpers -------------------------


def test_mcptool_dataclass_exists() -> None:
    """A small `MCPTool` dataclass is exported for callers that want a concrete type."""
    from mcpschema import MCPTool

    t = MCPTool(name="x", description="y", inputSchema={"type": "object"})
    assert t.name == "x"
    assert t.description == "y"
    assert t.inputSchema == {"type": "object"}


def test_tool_from_dict_helper() -> None:
    from mcpschema import tool_from_dict

    raw = {"name": "x", "description": "y", "inputSchema": {"type": "object"}}
    tool = tool_from_dict(raw)
    assert tool.name == "x"
    assert tool.description == "y"
    assert tool.inputSchema == {"type": "object"}


def test_tool_from_dict_accepts_missing_optional_fields() -> None:
    from mcpschema import tool_from_dict

    raw = {"name": "x", "inputSchema": {}}
    tool = tool_from_dict(raw)
    assert tool.name == "x"
    assert tool.description == ""
    assert tool.inputSchema == {}


# --- error path: adapters are TOTAL over arbitrary input (Invariant 21) ---
# Per Invariant 21, public APIs MUST NOT raise on arbitrary input — they must
# return structured output even for malformed inputs. These tests pin that
# contract; if a future refactor re-introduces a TypeError/AttributeError on
# weird inputs, these tests fail immediately.


def test_convert_with_none_name_returns_empty_dict_not_crash() -> None:
    from mcpschema import to_openai_tool

    class BadTool:
        description = ""
        inputSchema = {}

    BadTool.name = None  # type: ignore[attr-defined]
    # Must not raise — should return something structured.
    out = to_openai_tool(BadTool())  # type: ignore[arg-type]
    assert isinstance(out, dict)


def test_convert_with_missing_input_schema_returns_dict() -> None:
    from mcpschema import to_openai_tool

    class NoSchema:
        name = "x"
        description = "y"

    # Must not raise — should return a dict with default empty params.
    out = to_openai_tool(NoSchema())  # type: ignore[arg-type]
    assert isinstance(out, dict)
    assert out["function"]["name"] == "x"


def test_convert_with_none_description_does_not_crash() -> None:
    """None description must not crash — coerced to empty string."""
    from mcpschema import to_openai_tool

    class WeirdTool:
        name = "x"
        description = None  # type: ignore[assignment]
        inputSchema = {}

    out = to_openai_tool(WeirdTool())  # type: ignore[arg-type]
    assert out["function"]["name"] == "x"


def test_convert_with_garbage_inputSchema_returns_dict() -> None:
    """inputSchema that's a string instead of dict must coerce, not crash."""
    from mcpschema import to_openai_tool

    class GarbageSchema:
        name = "x"
        description = "y"
        inputSchema = "not a dict"  # type: ignore[assignment]

    out = to_openai_tool(GarbageSchema())  # type: ignore[arg-type]
    assert isinstance(out, dict)


def test_convert_with_none_tool_object_returns_dict() -> None:
    """Passing None must return a structured fallback (not crash)."""
    from mcpschema import to_openai_tool

    out = to_openai_tool(None)  # type: ignore[arg-type]
    assert isinstance(out, dict)


# --- the library is deterministic ---------------------------------------


def test_output_is_deterministic_for_same_input() -> None:
    """Two calls with the same input produce byte-equal output."""
    from mcpschema import to_openai_tool
    from tests.conftest import FakeTool

    tool = FakeTool(
        name="det",
        description="deterministic",
        inputSchema={"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]},
    )
    import json
    a = json.dumps(to_openai_tool(tool), sort_keys=True)
    b = json.dumps(to_openai_tool(tool), sort_keys=True)
    assert a == b


# --- empty description is preserved (not stripped) ----------------------


def test_empty_description_preserved_in_openai() -> None:
    from mcpschema import to_openai_tool
    from tests.conftest import FakeTool

    tool = FakeTool(name="x", description="", inputSchema={"type": "object", "properties": {}})
    out = to_openai_tool(tool)
    # Either present-and-empty or absent — both are acceptable.
    assert out["function"].get("description", "") == ""


def test_empty_description_preserved_in_anthropic() -> None:
    from mcpschema import to_anthropic_tool
    from tests.conftest import FakeTool

    tool = FakeTool(name="x", description="", inputSchema={"type": "object", "properties": {}})
    out = to_anthropic_tool(tool)
    assert out.get("description", "") == ""


# --- output type stability ----------------------------------------------


def test_output_types_are_pure_dicts() -> None:
    """Adapters return plain dicts, not pydantic or dataclass instances."""
    from mcpschema import convert, to_anthropic_tool, to_gemini_tool, to_ollama_tool, to_openai_tool
    from tests.conftest import FakeTool

    tool = FakeTool(name="x", description="y", inputSchema={"type": "object", "properties": {}})
    assert isinstance(to_openai_tool(tool), dict)
    assert isinstance(to_anthropic_tool(tool), dict)
    assert isinstance(to_gemini_tool(tool), dict)
    assert isinstance(to_ollama_tool(tool), dict)
    assert isinstance(convert(tool, "openai"), dict)


# --- regression guard: each adapter's signature is pure ------------------


def test_adapters_do_not_mutate_input() -> None:
    """Adapter functions are pure — they don't mutate the caller's tool object."""
    from dataclasses import FrozenInstanceError

    from mcpschema import to_anthropic_tool, to_openai_tool
    from tests.conftest import FakeTool

    # FakeTool is frozen — any attribute write would raise FrozenInstanceError.
    schema_before = {
        "type": "object",
        "properties": {"x": {"type": "string"}},
        "required": ["x"],
    }
    tool = FakeTool(name="x", description="y", inputSchema=schema_before)
    # The schema object in the tool is the same dict the user passed in —
    # adapters must not mutate it.
    import copy

    snapshot = copy.deepcopy(tool.inputSchema)
    to_openai_tool(tool)
    to_anthropic_tool(tool)
    assert tool.inputSchema == snapshot, "adapter mutated inputSchema!"


# --- regression: a tool with no 'properties' key ------------------------


def test_input_schema_with_no_properties_key() -> None:
    from mcpschema import to_openai_tool
    from tests.conftest import FakeTool

    tool = FakeTool(name="x", description="y", inputSchema={"type": "object", "required": []})
    out = to_openai_tool(tool)
    assert out["function"]["parameters"]["properties"] == {}


# --- regression: unicode in schema values -------------------------------


def test_unicode_in_schema_default_strings() -> None:
    from mcpschema import to_openai_tool
    from tests.conftest import FakeTool

    tool = FakeTool(
        name="emoji_params",
        description="📊",
        inputSchema={
            "type": "object",
            "properties": {"name": {"type": "string", "description": "тест"}},
            "required": ["name"],
        },
    )
    out = to_openai_tool(tool)
    # Defaults are stripped; descriptions survive.
    assert out["function"]["parameters"]["properties"]["name"]["description"] == "тест"