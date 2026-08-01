"""Tests for the Anthropic adapter — acceptance criteria #5, #6, #22."""

from __future__ import annotations

from mcpschema import to_anthropic_tool

from .conftest import FakeTool, make_tool


# --- AC #5: basic MCP tool → Anthropic tool_use shape ----------------------


def test_to_anthropic_tool_basic(basic_tool: FakeTool) -> None:
    out = to_anthropic_tool(basic_tool)
    assert out["name"] == "git_log"
    assert out["description"] == "Get recent commits"
    assert "input_schema" in out
    schema = out["input_schema"]
    assert schema["type"] == "object"
    assert "n" in schema["properties"]


def test_to_anthropic_tool_required_fields(basic_tool: FakeTool) -> None:
    out = to_anthropic_tool(basic_tool)
    schema = out["input_schema"]
    assert schema["required"] == ["n"]


def test_to_anthropic_tool_no_top_level_required_omits_key() -> None:
    tool = FakeTool(
        name="opt",
        description="Optional only",
        inputSchema={"type": "object", "properties": {"x": {"type": "integer"}}, "required": []},
    )
    out = to_anthropic_tool(tool)
    schema = out["input_schema"]
    assert "required" not in schema or schema["required"] == []


# --- AC #6: nested properties become nested input_schema ------------------


def test_to_anthropic_tool_nested_object(nested_tool: FakeTool) -> None:
    out = to_anthropic_tool(nested_tool)
    schema = out["input_schema"]
    assert schema["properties"]["filter"]["type"] == "object"
    inner = schema["properties"]["filter"]
    assert "tag" in inner["properties"]
    assert inner["properties"]["tag"]["type"] == "string"
    assert inner["required"] == ["tag"]


# --- AC #22: 3-level nested object ---------------------------------------


def test_anthropic_deeply_nested_object(deeply_nested_tool: FakeTool) -> None:
    out = to_anthropic_tool(deeply_nested_tool)
    schema = out["input_schema"]
    # Anthropic accepts nested objects up to ~3 levels natively.
    level1 = schema["properties"]["level1"]
    assert level1["type"] == "object"
    level2 = level1["properties"]["level2"]
    assert level2["type"] == "object"
    level3 = level2["properties"]["level3"]
    assert level3["type"] == "string"


# --- defaults handled like OpenAI (omitted) ------------------------------


def test_to_anthropic_tool_omits_defaults(basic_tool: FakeTool) -> None:
    out = to_anthropic_tool(basic_tool)
    n_schema = out["input_schema"]["properties"]["n"]
    assert "default" not in n_schema


def test_to_anthropic_tool_empty_input_schema() -> None:
    tool = FakeTool(name="ping", description="health", inputSchema={})
    out = to_anthropic_tool(tool)
    assert out["name"] == "ping"
    assert out["input_schema"]["type"] == "object"
    assert out["input_schema"].get("properties", {}) == {}


# --- unicode handling -----------------------------------------------------


def test_to_anthropic_tool_unicode_description() -> None:
    tool = FakeTool(
        name="emoji",
        description="🎯 Target — тест",
        inputSchema={"type": "object", "properties": {}, "required": []},
    )
    out = to_anthropic_tool(tool)
    assert out["description"] == "🎯 Target — тест"


# --- property type mapping (sanity) ---------------------------------------


def test_to_anthropic_tool_property_types_present() -> None:
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
                "o": {"type": "object"},
            },
            "required": [],
        },
    )
    out = to_anthropic_tool(tool)
    props = out["input_schema"]["properties"]
    assert props["s"]["type"] == "string"
    assert props["i"]["type"] == "integer"
    assert props["n"]["type"] == "number"
    assert props["b"]["type"] == "boolean"
    assert props["a"]["type"] == "array"
    assert props["a"]["items"]["type"] == "string"
    assert props["o"]["type"] == "object"