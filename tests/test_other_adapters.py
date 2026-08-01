"""Tests for the additional adapters: deepseek, mistral."""

from __future__ import annotations

from mcpschema import to_deepseek_tool, to_mistral_tool

from .conftest import FakeTool


# --- deepseek is OpenAI-compatible (same shape) ----------------------------


def test_to_deepseek_tool_basic(basic_tool: FakeTool) -> None:
    out = to_deepseek_tool(basic_tool)
    assert out["type"] == "function"
    assert out["function"]["name"] == "git_log"
    assert out["function"]["description"] == "Get recent commits"
    assert "parameters" in out["function"]


def test_to_deepseek_tool_required(basic_tool: FakeTool) -> None:
    out = to_deepseek_tool(basic_tool)
    assert out["function"]["parameters"]["required"] == ["n"]


def test_to_deepseek_tool_omits_defaults(basic_tool: FakeTool) -> None:
    out = to_deepseek_tool(basic_tool)
    assert "default" not in out["function"]["parameters"]["properties"]["n"]


# --- mistral is OpenAI-compatible (same shape) ----------------------------


def test_to_mistral_tool_basic(basic_tool: FakeTool) -> None:
    out = to_mistral_tool(basic_tool)
    assert out["type"] == "function"
    assert out["function"]["name"] == "git_log"
    assert "parameters" in out["function"]


def test_to_mistral_tool_required(basic_tool: FakeTool) -> None:
    out = to_mistral_tool(basic_tool)
    assert out["function"]["parameters"]["required"] == ["n"]


def test_to_mistral_tool_omits_defaults(basic_tool: FakeTool) -> None:
    out = to_mistral_tool(basic_tool)
    assert "default" not in out["function"]["parameters"]["properties"]["n"]


# --- both adapters are not the same function (different impls even if same shape) -


def test_to_deepseek_and_to_mistral_are_distinct_callables() -> None:
    assert to_deepseek_tool is not to_mistral_tool
    assert callable(to_deepseek_tool)
    assert callable(to_mistral_tool)


# --- empty schema works for both -----------------------------------------


def test_to_deepseek_tool_empty_tool() -> None:
    tool = FakeTool(name="ping", description="health", inputSchema={})
    out = to_deepseek_tool(tool)
    assert out["function"]["name"] == "ping"
    assert out["function"]["parameters"]["type"] == "object"


def test_to_mistral_tool_empty_tool() -> None:
    tool = FakeTool(name="ping", description="health", inputSchema={})
    out = to_mistral_tool(tool)
    assert out["function"]["name"] == "ping"
    assert out["function"]["parameters"]["type"] == "object"


# --- unicode description roundtrip ---------------------------------------


def test_deepseek_unicode_description() -> None:
    tool = FakeTool(name="rocket", description="🚀 launch", inputSchema={"type": "object", "properties": {}})
    out = to_deepseek_tool(tool)
    assert out["function"]["description"] == "🚀 launch"


def test_mistral_unicode_description() -> None:
    tool = FakeTool(name="rocket", description="🚀 launch", inputSchema={"type": "object", "properties": {}})
    out = to_mistral_tool(tool)
    assert out["function"]["description"] == "🚀 launch"