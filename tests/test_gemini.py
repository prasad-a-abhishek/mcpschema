"""Tests for the Gemini adapter — acceptance criteria #7, #8, #22."""

from __future__ import annotations

from mcpschema import to_gemini_tool

from .conftest import FakeTool


# --- AC #7: basic MCP tool → Gemini FunctionDeclaration --------------------


def test_to_gemini_tool_basic(basic_tool: FakeTool) -> None:
    out = to_gemini_tool(basic_tool)
    # Gemini uses FunctionDeclaration shape: name + description + parameters
    assert "name" in out
    assert out["name"] == "git_log"
    assert out.get("description") == "Get recent commits"
    assert "parameters" in out
    params = out["parameters"]
    # Gemini's type is uppercase (OBJECT/STRING/etc)
    assert params["type"] == "OBJECT"
    assert "n" in params["properties"]


# --- AC #8: required fields map to Gemini required ------------------------


def test_to_gemini_tool_required_properties(basic_tool: FakeTool) -> None:
    out = to_gemini_tool(basic_tool)
    params = out["parameters"]
    assert params["required"] == ["n"]


def test_to_gemini_tool_no_required_omits_key() -> None:
    tool = FakeTool(
        name="opt",
        description="all opt",
        inputSchema={"type": "object", "properties": {"x": {"type": "string"}}, "required": []},
    )
    out = to_gemini_tool(tool)
    params = out["parameters"]
    assert "required" not in params or params["required"] == []


# --- AC #22: nested objects preserved as OBJECTs -------------------------


def test_to_gemini_tool_nested_object(nested_tool: FakeTool) -> None:
    out = to_gemini_tool(nested_tool)
    params = out["parameters"]
    filter_schema = params["properties"]["filter"]
    assert filter_schema["type"] == "OBJECT"
    inner = filter_schema["properties"]
    assert "tag" in inner
    # Gemini uppercase types
    assert inner["tag"]["type"] == "STRING"


def test_gemini_deeply_nested_object(deeply_nested_tool: FakeTool) -> None:
    out = to_gemini_tool(deeply_nested_tool)
    params = out["parameters"]
    level1 = params["properties"]["level1"]
    assert level1["type"] == "OBJECT"
    level2 = level1["properties"]["level2"]
    assert level2["type"] == "OBJECT"
    assert level2["properties"]["level3"]["type"] == "STRING"


# --- defaults are omitted (Gemini doesn't accept defaults in FunctionDeclaration) ----


def test_to_gemini_tool_omits_defaults(basic_tool: FakeTool) -> None:
    out = to_gemini_tool(basic_tool)
    n_schema = out["parameters"]["properties"]["n"]
    assert "default" not in n_schema


# --- type uppercase conversion -----------------------------------------


def test_to_gemini_tool_uppercase_types() -> None:
    tool = FakeTool(
        name="typed",
        description="Type sweep",
        inputSchema={
            "type": "object",
            "properties": {
                "s": {"type": "string"},
                "i": {"type": "integer"},
                "n": {"type": "number"},
                "b": {"type": "boolean"},
                "a": {"type": "array", "items": {"type": "string"}},
            },
            "required": [],
        },
    )
    out = to_gemini_tool(tool)
    props = out["parameters"]["properties"]
    assert props["s"]["type"] == "STRING"
    assert props["i"]["type"] == "INTEGER"
    assert props["n"]["type"] == "NUMBER"
    assert props["b"]["type"] == "BOOLEAN"
    assert props["a"]["type"] == "ARRAY"


# --- empty tool ----------------------------------------------------------


def test_to_gemini_tool_empty_input_schema() -> None:
    tool = FakeTool(name="ping", description="health", inputSchema={})
    out = to_gemini_tool(tool)
    assert out["name"] == "ping"
    assert out["parameters"]["type"] == "OBJECT"
    assert out["parameters"].get("properties", {}) == {}


# --- description empty string is preserved (Gemini accepts empty description) --


def test_to_gemini_tool_empty_description() -> None:
    tool = FakeTool(name="x", description="", inputSchema={"type": "object", "properties": {}, "required": []})
    out = to_gemini_tool(tool)
    assert out["name"] == "x"
    # description may be empty string or omitted — both are acceptable
    assert out.get("description", "") == ""