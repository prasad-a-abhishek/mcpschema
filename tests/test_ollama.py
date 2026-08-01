"""Tests for the Ollama adapter — acceptance criteria #9, #10."""

from __future__ import annotations

from mcpschema import to_ollama_tool

from .conftest import FakeTool


# --- AC #9: basic MCP tool → Ollama tool format --------------------------


def test_to_ollama_tool_basic(basic_tool: FakeTool) -> None:
    out = to_ollama_tool(basic_tool)
    # Ollama's tool-call format wraps the schema in a 'type'/'function' pair
    assert out.get("type") == "function"
    fn = out["function"]
    assert fn["name"] == "git_log"
    assert fn["description"] == "Get recent commits"
    assert "parameters" in fn


def test_to_ollama_tool_required_fields(basic_tool: FakeTool) -> None:
    out = to_ollama_tool(basic_tool)
    fn = out["function"]
    params = fn["parameters"]
    assert params.get("required") == ["n"]


# --- AC #10: system prompt suffix includes tool description + schema ----


def test_to_ollama_tool_system_prompt(basic_tool: FakeTool) -> None:
    out = to_ollama_tool(basic_tool)
    # We bundle the description and schema in a system-prompt-suffix field so
    # users can append it to their system prompt when calling Ollama.
    suffix = out.get("system_prompt_suffix", "")
    assert "git_log" in suffix
    assert "Get recent commits" in suffix
    # The schema is also referenced (as JSON or as a human-readable summary)
    assert ("parameters" in suffix) or ("n" in suffix) or ("number of commits" in suffix.lower())


def test_to_ollama_tool_system_prompt_includes_param_names() -> None:
    """The system prompt suffix must mention each parameter by name."""
    tool = FakeTool(
        name="multi",
        description="Multi-param tool",
        inputSchema={
            "type": "object",
            "properties": {
                "alpha": {"type": "string", "description": "First param"},
                "beta": {"type": "integer", "description": "Second param"},
            },
            "required": ["alpha"],
        },
    )
    out = to_ollama_tool(tool)
    suffix = out.get("system_prompt_suffix", "")
    assert "alpha" in suffix
    assert "beta" in suffix


# --- defaults are omitted -------------------------------------------------


def test_to_ollama_tool_omits_defaults(basic_tool: FakeTool) -> None:
    out = to_ollama_tool(basic_tool)
    fn = out["function"]
    n_schema = fn["parameters"]["properties"]["n"]
    assert "default" not in n_schema


# --- empty schema --------------------------------------------------------


def test_to_ollama_tool_empty_input_schema() -> None:
    tool = FakeTool(name="ping", description="health", inputSchema={})
    out = to_ollama_tool(tool)
    assert out["type"] == "function"
    assert out["function"]["name"] == "ping"


# --- nested objects ------------------------------------------------------


def test_to_ollama_tool_nested_object(nested_tool: FakeTool) -> None:
    out = to_ollama_tool(nested_tool)
    fn = out["function"]
    assert fn["parameters"]["properties"]["filter"]["type"] == "object"