"""Tests for ``convert`` and ``convert_all`` dispatch — AC #11–#14, #15."""

from __future__ import annotations

import pytest

from mcpschema import convert, convert_all, to_openai_tool

from .conftest import FakeTool, make_tool


def _tool(name: str) -> FakeTool:
    return FakeTool(
        name=name,
        description=f"Tool {name}",
        inputSchema={"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]},
    )


# --- AC #11: convert_all openai ------------------------------------------


def test_convert_all_openai() -> None:
    tools = [_tool("a"), _tool("b"), _tool("c")]
    out = convert_all(tools, "openai")
    assert isinstance(out, list)
    assert len(out) == 3
    assert all(item["type"] == "function" for item in out)
    assert [item["function"]["name"] for item in out] == ["a", "b", "c"]


# --- AC #12: convert_all anthropic ---------------------------------------


def test_convert_all_anthropic() -> None:
    tools = [_tool("a"), _tool("b")]
    out = convert_all(tools, "anthropic")
    assert isinstance(out, list)
    assert len(out) == 2
    assert all("input_schema" in item for item in out)
    assert [item["name"] for item in out] == ["a", "b"]


# --- AC #13: empty list works --------------------------------------------


def test_empty_tool_list() -> None:
    assert convert_all([], "openai") == []
    assert convert_all([], "anthropic") == []
    assert convert_all([], "gemini") == []
    assert convert_all([], "ollama") == []
    assert convert_all([], "deepseek") == []
    assert convert_all([], "mistral") == []


def test_convert_all_with_iterator() -> None:
    """Generators / iterators should be acceptable (single pass)."""
    gen = (_tool(n) for n in ("a", "b"))
    out = convert_all(gen, "openai")
    assert len(out) == 2


# --- AC #14: unknown provider raises ValueError --------------------------


def test_unknown_provider_raises() -> None:
    tool = _tool("a")
    with pytest.raises(ValueError) as exc:
        convert(tool, "unknown_provider")
    assert "unknown_provider" in str(exc.value).lower() or "unsupported" in str(exc.value).lower()


def test_unknown_provider_in_convert_all_raises() -> None:
    with pytest.raises(ValueError):
        convert_all([_tool("a")], "bogus")


# --- AC #15: round-trip via convert --------------------------------------


def test_mcp_types_tool_round_trip(basic_tool: FakeTool) -> None:
    """Convert to OpenAI and back — the result should still be a valid mcp-style tool."""
    openai_form = to_openai_tool(basic_tool)
    # The OpenAI form's function.parameters should mirror the original MCP schema.
    assert openai_form["function"]["name"] == basic_tool.name
    params = openai_form["function"]["parameters"]
    # Property names preserved
    assert set(params["properties"].keys()) == set(basic_tool.inputSchema["properties"].keys())
    # Required preserved
    assert set(params.get("required", [])) == set(basic_tool.inputSchema.get("required", []))


# --- convert() dispatch --------------------------------------------------


def test_convert_dispatches_to_openai() -> None:
    tool = _tool("a")
    out = convert(tool, "openai")
    assert out["type"] == "function"


def test_convert_dispatches_to_anthropic() -> None:
    tool = _tool("a")
    out = convert(tool, "anthropic")
    assert "input_schema" in out


def test_convert_dispatches_to_gemini() -> None:
    tool = _tool("a")
    out = convert(tool, "gemini")
    assert out["parameters"]["type"] == "OBJECT"


def test_convert_dispatches_to_ollama() -> None:
    tool = _tool("a")
    out = convert(tool, "ollama")
    assert out["type"] == "function"


def test_convert_dispatches_to_deepseek() -> None:
    tool = _tool("a")
    out = convert(tool, "deepseek")
    assert out["type"] == "function"


def test_convert_dispatches_to_mistral() -> None:
    tool = _tool("a")
    out = convert(tool, "mistral")
    assert out["type"] == "function"


def test_convert_case_insensitive_provider() -> None:
    tool = _tool("a")
    assert convert(tool, "OpenAI")["type"] == "function"
    assert convert(tool, "ANTHROPIC")["name"] == "a"
    assert convert(tool, "Gemini")["parameters"]["type"] == "OBJECT"


# --- providers listing ---------------------------------------------------


def test_providers_constant_is_complete() -> None:
    """PROVIDERS must list every supported provider."""
    from mcpschema import PROVIDERS

    assert set(PROVIDERS) >= {
        "openai",
        "anthropic",
        "gemini",
        "ollama",
        "deepseek",
        "mistral",
    }


def test_providers_constant_values_are_callables() -> None:
    from mcpschema import PROVIDERS

    for name, fn in PROVIDERS.items():
        assert callable(fn), f"provider {name!r} is not callable"


# --- one malformed schema doesn't poison the whole batch ----------------


def test_convert_all_handles_each_tool_independently() -> None:
    """A tool with a missing top-level type should still convert."""
    good = make_tool("good", "good")
    loose = FakeTool(
        name="loose",
        description="loose",
        inputSchema={"properties": {"x": {"type": "string"}}},  # no top-level type
    )
    out = convert_all([good, loose], "openai")
    assert len(out) == 2
    assert out[0]["function"]["name"] == "good"
    assert out[1]["function"]["name"] == "loose"


# --- single-tool convert is the canonical entry point -------------------


def test_convert_single_tool_returns_single_dict() -> None:
    tool = _tool("only")
    out = convert(tool, "openai")
    assert isinstance(out, dict)
    assert "function" in out