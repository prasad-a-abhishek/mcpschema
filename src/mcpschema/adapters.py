"""Public adapter functions and the ``convert`` / ``convert_all`` dispatch."""

from __future__ import annotations

from typing import Any, Callable, Iterable

from mcpschema._schema import (
    build_anthropic_input_schema,
    build_gemini_parameters,
    build_ollama_system_prompt_suffix,
    build_openai_function,
)


def to_openai_tool(tool: Any) -> dict[str, Any]:
    """Convert an MCP-style tool to OpenAI's function-call shape.

    Returns a dict with ``{"type": "function", "function": {...}}``.
    Defaults are stripped per OpenAI's API spec (AC #4).
    """
    return {"type": "function", "function": build_openai_function(tool)}


def to_anthropic_tool(tool: Any) -> dict[str, Any]:
    """Convert an MCP-style tool to Anthropic's tool_use shape.

    Returns a dict with ``{"name", "description", "input_schema"}``.
    """
    return {
        "name": getattr(tool, "name", ""),
        "description": getattr(tool, "description", "") or "",
        "input_schema": build_anthropic_input_schema(tool),
    }


def to_gemini_tool(tool: Any) -> dict[str, Any]:
    """Convert an MCP-style tool to Gemini's FunctionDeclaration shape.

    Returns a dict with ``{"name", "description", "parameters"}`` where
    parameter types are uppercase (STRING, INTEGER, OBJECT, etc.).
    """
    desc = getattr(tool, "description", "") or ""
    out: dict[str, Any] = {
        "name": getattr(tool, "name", ""),
        "parameters": build_gemini_parameters(tool),
    }
    if desc:
        out["description"] = desc
    return out


def to_ollama_tool(tool: Any) -> dict[str, Any]:
    """Convert an MCP-style tool to Ollama's tool-call shape.

    Ollama's tool-call format mirrors OpenAI's, but we also bundle a
    ``system_prompt_suffix`` field with a human-readable summary that
    helps local models that consume the system prompt directly.
    """
    out = to_openai_tool(tool)
    out["system_prompt_suffix"] = build_ollama_system_prompt_suffix(tool)
    return out


def to_deepseek_tool(tool: Any) -> dict[str, Any]:
    """Convert an MCP-style tool to DeepSeek's tool-call shape.

    DeepSeek's API is OpenAI-compatible; we use the same builder.
    """
    return to_openai_tool(tool)


def to_mistral_tool(tool: Any) -> dict[str, Any]:
    """Convert an MCP-style tool to Mistral's tool-call shape.

    Mistral's API is OpenAI-compatible; we use the same builder.
    """
    return to_openai_tool(tool)


# --- Provider registry & dispatch ----------------------------------------


PROVIDERS: dict[str, Callable[[Any], dict[str, Any]]] = {
    "openai": to_openai_tool,
    "anthropic": to_anthropic_tool,
    "gemini": to_gemini_tool,
    "ollama": to_ollama_tool,
    "deepseek": to_deepseek_tool,
    "mistral": to_mistral_tool,
}


def _resolve_provider(name: str) -> Callable[[Any], dict[str, Any]]:
    key = name.lower().strip()
    fn = PROVIDERS.get(key)
    if fn is None:
        raise ValueError(
            f"unsupported provider {name!r}; supported: {sorted(PROVIDERS.keys())}"
        )
    return fn


def convert(tool: Any, provider: str) -> dict[str, Any]:
    """Convert one tool to the named provider's format.

    Provider names are case-insensitive. Raises ``ValueError`` on unknown.
    """
    return _resolve_provider(provider)(tool)


def convert_all(tools: Iterable[Any], provider: str) -> list[dict[str, Any]]:
    """Convert an iterable of MCP tools to the named provider's format.

    Accepts any iterable (list, generator, itertools.chain, etc.). Empty
    input → empty output.
    """
    fn = _resolve_provider(provider)
    return [fn(t) for t in tools]