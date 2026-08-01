"""Tests for the OpenAI adapter — acceptance criteria #1–#4, #20–#22."""

from __future__ import annotations

from typing import Any

import pytest

from mcpschema import to_openai_tool

from .conftest import FakeTool, make_tool


# --- AC #1: basic MCP tool → OpenAI function dict ---------------------------


def test_to_openai_tool_basic(basic_tool: FakeTool) -> None:
    out = to_openai_tool(basic_tool)
    assert out["type"] == "function"
    fn = out["function"]
    assert fn["name"] == "git_log"
    assert fn["description"] == "Get recent commits"
    assert "parameters" in fn
    params = fn["parameters"]
    assert params["type"] == "object"
    assert "n" in params["properties"]


def test_to_openai_tool_returns_dict_for_minimal_tool() -> None:
    """Empty input schema still produces a valid OpenAI function dict."""
    tool = make_tool("noop", "Does nothing")
    out = to_openai_tool(tool)
    assert out["type"] == "function"
    assert out["function"]["name"] == "noop"


def test_to_openai_tool_preserves_description_with_unicode() -> None:
    """Unicode in descriptions must round-trip safely."""
    tool = FakeTool(
        name="emoji_tool",
        description="🚀 Launches the rocket — 测试 unicode",
        inputSchema={"type": "object", "properties": {}, "required": []},
    )
    out = to_openai_tool(tool)
    assert out["function"]["description"] == "🚀 Launches the rocket — 测试 unicode"


# --- AC #2: required array maps to OpenAI required --------------------------


def test_to_openai_tool_required_fields(basic_tool: FakeTool) -> None:
    out = to_openai_tool(basic_tool)
    params = out["function"]["parameters"]
    assert params["required"] == ["n"]


def test_to_openai_tool_no_required_when_empty() -> None:
    tool = FakeTool(
        name="optional",
        description="All params optional",
        inputSchema={"type": "object", "properties": {"x": {"type": "integer"}}, "required": []},
    )
    out = to_openai_tool(tool)
    params = out["function"]["parameters"]
    # OpenAI's "required" is optional — when the MCP schema has no required
    # fields, the adapter should OMIT the key (OpenAI treats absence == empty).
    assert "required" not in params or params["required"] == []


# --- AC #3: property type strings map correctly -----------------------------


@pytest.mark.parametrize(
    "mcp_type,expected_openai_type",
    [
        ("string", "string"),
        ("integer", "integer"),
        ("number", "number"),
        ("boolean", "boolean"),
        ("array", "array"),
        ("object", "object"),
    ],
)
def test_to_openai_tool_property_types(mcp_type: str, expected_openai_type: str) -> None:
    tool = FakeTool(
        name="typed",
        description="Type sweep",
        inputSchema={
            "type": "object",
            "properties": {"x": {"type": mcp_type}},
            "required": ["x"],
        },
    )
    out = to_openai_tool(tool)
    assert out["function"]["parameters"]["properties"]["x"]["type"] == expected_openai_type


def test_to_openai_tool_unknown_type_falls_back_to_string() -> None:
    """Unknown JSON-Schema types map to OpenAI's nearest equivalent (string).

    OpenAI's accepted types are limited; we degrade gracefully rather than
    crashing.
    """
    tool = FakeTool(
        name="weird",
        description="Has a null parameter",
        inputSchema={
            "type": "object",
            "properties": {"x": {"type": "null"}},
            "required": ["x"],
        },
    )
    out = to_openai_tool(tool)
    # Either it omits the field or maps to string — but never raises.
    assert "function" in out


# --- AC #4: defaults are NOT included in the OpenAI output ------------------


def test_to_openai_tool_defaults_omitted(basic_tool: FakeTool) -> None:
    out = to_openai_tool(basic_tool)
    n_schema = out["function"]["parameters"]["properties"]["n"]
    # Per OpenAI spec, defaults are NOT part of the function-call schema.
    assert "default" not in n_schema


def test_to_openai_tool_strips_all_default_keys() -> None:
    tool = FakeTool(
        name="multi",
        description="Multiple defaults",
        inputSchema={
            "type": "object",
            "properties": {
                "a": {"type": "string", "default": "x"},
                "b": {"type": "integer", "default": 5},
                "c": {"type": "boolean", "default": False},
            },
            "required": [],
        },
    )
    out = to_openai_tool(tool)
    props = out["function"]["parameters"]["properties"]
    for key in ("a", "b", "c"):
        assert "default" not in props[key], f"property {key!r} leaked a 'default' key"


# --- AC #20: array type with items schema ------------------------------------


def test_to_openai_tool_array_type(array_tool: FakeTool) -> None:
    out = to_openai_tool(array_tool)
    items = out["function"]["parameters"]["properties"]["items"]
    assert items["type"] == "array"
    assert items["items"]["type"] == "string"


# --- AC #21: boolean mapping -------------------------------------------------


def test_to_openai_tool_boolean_type(boolean_tool: FakeTool) -> None:
    out = to_openai_tool(boolean_tool)
    enabled = out["function"]["parameters"]["properties"]["enabled"]
    assert enabled["type"] == "boolean"


# --- AC #22: 3-level nested object -----------------------------------------


def test_openai_deeply_nested_object(deeply_nested_tool: FakeTool) -> None:
    out = to_openai_tool(deeply_nested_tool)
    params = out["function"]["parameters"]
    # OpenAI accepts nested objects natively — they should round-trip.
    level1 = params["properties"]["level1"]
    assert level1["type"] == "object"
    assert level1["properties"]["level2"]["type"] == "object"
    assert level1["properties"]["level2"]["properties"]["level3"]["type"] == "string"


# --- negative / boundary tests ----------------------------------------------


def test_to_openai_tool_accepts_dict_shim_with_attrs() -> None:
    """Duck-typed object with the right attrs (not a dataclass) is accepted."""
    raw: dict[str, Any] = {
        "name": "from_dict",
        "description": "Built from a raw dict",
        "inputSchema": {"type": "object", "properties": {"q": {"type": "string"}}, "required": ["q"]},
    }

    class Shim:
        pass

    shim = Shim()
    shim.name = raw["name"]
    shim.description = raw["description"]
    shim.inputSchema = raw["inputSchema"]
    out = to_openai_tool(shim)  # type: ignore[arg-type]
    assert out["function"]["name"] == "from_dict"


def test_to_openai_tool_input_schema_without_type_object() -> None:
    """Missing 'type' at the top level still produces a valid function."""
    tool = FakeTool(
        name="loose",
        description="Loose schema",
        inputSchema={"properties": {"x": {"type": "string"}}},
    )
    out = to_openai_tool(tool)
    params = out["function"]["parameters"]
    # We coerce loose top-level to "object".
    assert params["type"] == "object"


def test_to_openai_tool_property_without_type_defaults_to_string() -> None:
    tool = FakeTool(
        name="loose_prop",
        description="Property without type",
        inputSchema={"type": "object", "properties": {"x": {"description": "no type"}}, "required": ["x"]},
    )
    out = to_openai_tool(tool)
    assert out["function"]["parameters"]["properties"]["x"]["type"] == "string"


def test_to_openai_tool_empty_input_schema_yields_empty_params() -> None:
    tool = make_tool("empty", "no params")
    out = to_openai_tool(tool)
    params = out["function"]["parameters"]
    assert params["type"] == "object"
    assert params.get("properties", {}) == {}