"""Internal helpers — schema normalization and provider-format builders.

These are NOT exported. Public consumers should use the per-provider adapter
functions (``to_openai_tool``, ``to_anthropic_tool``, etc.) in
``mcpschema.adapters``.
"""

from __future__ import annotations

from typing import Any

# Map of JSON-Schema primitive types to OpenAI-compatible parameter types.
# OpenAI accepts: string, integer, number, boolean, array, object, null.
_OPENAI_TYPES: dict[str, str] = {
    "string": "string",
    "integer": "integer",
    "number": "number",
    "boolean": "boolean",
    "array": "array",
    "object": "object",
    "null": "string",  # degrade unknown/null → string rather than crash
}

# Gemini uppercases its type strings.
_GEMINI_TYPES: dict[str, str] = {
    "string": "STRING",
    "integer": "INTEGER",
    "number": "NUMBER",
    "boolean": "BOOLEAN",
    "array": "ARRAY",
    "object": "OBJECT",
    "null": "STRING",
}


def _get_schema(tool: Any) -> dict[str, Any]:
    """Return the tool's inputSchema as a dict (never None)."""
    schema = getattr(tool, "inputSchema", None)
    return schema if isinstance(schema, dict) else {}


def _get_name(tool: Any) -> str:
    """Return the tool's name, or '' for malformed input (Invariant 21: total)."""
    name = getattr(tool, "name", None)
    if isinstance(name, str) and name:
        return name
    return ""


def _get_description(tool: Any) -> str:
    """Return the tool's description, or '' for malformed input."""
    desc = getattr(tool, "description", None)
    return desc if isinstance(desc, str) else ""


def _normalize_property(prop: Any, type_map: dict[str, str]) -> dict[str, Any]:
    """Normalize a single property schema for a given provider.

    Strips MCP-specific keys (``default`` is the only one our spec cares about),
    normalizes the ``type`` field via ``type_map``, and preserves ``items``,
    ``properties``, and ``description`` as-is.
    """
    if not isinstance(prop, dict):
        # Malformed property — coerce to empty string property.
        return {"type": "string"}

    out: dict[str, Any] = {}
    raw_type = prop.get("type")
    if isinstance(raw_type, str) and raw_type in type_map:
        out["type"] = type_map[raw_type]
    else:
        # No type, or unknown type — coerce to string.
        out["type"] = type_map.get("string", "string")

    # Preserve description if present and non-empty.
    desc = prop.get("description")
    if isinstance(desc, str) and desc:
        out["description"] = desc

    # Preserve items (for arrays).
    if "items" in prop and isinstance(prop["items"], dict):
        out["items"] = _normalize_property(prop["items"], type_map)

    # Preserve nested properties (for objects).
    if "properties" in prop and isinstance(prop["properties"], dict):
        nested_props: dict[str, Any] = {}
        for k, v in prop["properties"].items():
            nested_props[k] = _normalize_property(v, type_map)
        out["properties"] = nested_props
        # Preserve nested `required` array (for nested objects).
        nested_required = prop.get("required")
        if isinstance(nested_required, list) and nested_required:
            out["required"] = [str(r) for r in nested_required if isinstance(r, (str, int))]

    # Preserve enum if present.
    if "enum" in prop and isinstance(prop["enum"], list):
        out["enum"] = list(prop["enum"])

    # DO NOT copy `default` — per spec AC #4.
    # DO NOT copy `anyOf`, `oneOf`, `allOf` — not in provider formats.
    return out


def _normalize_schema(schema: dict[str, Any], type_map: dict[str, str]) -> dict[str, Any]:
    """Normalize the top-level inputSchema for a given provider."""
    raw_type = schema.get("type", "object")
    if not isinstance(raw_type, str):
        raw_type = "object"
    out: dict[str, Any] = {"type": type_map.get(raw_type, type_map["object"])}

    props = schema.get("properties")
    if isinstance(props, dict):
        out["properties"] = {k: _normalize_property(v, type_map) for k, v in props.items()}
    else:
        out["properties"] = {}

    required = schema.get("required")
    if isinstance(required, list) and required:
        # Preserve order, coerce all entries to strings.
        out["required"] = [str(r) for r in required if isinstance(r, (str, int))]
    # If required is missing or empty, we OMIT the key — most provider formats
    # treat absence as equivalent to empty.

    return out


def build_openai_function(tool: Any) -> dict[str, Any]:
    """Return the ``function`` dict for OpenAI/DeepSeek/Mistral."""
    return {
        "name": _get_name(tool),
        "description": _get_description(tool),
        "parameters": _normalize_schema(_get_schema(tool), _OPENAI_TYPES),
    }


def build_anthropic_input_schema(tool: Any) -> dict[str, Any]:
    """Return the Anthropic ``input_schema`` field."""
    return _normalize_schema(_get_schema(tool), _OPENAI_TYPES)


def build_gemini_parameters(tool: Any) -> dict[str, Any]:
    """Return the Gemini ``parameters`` field."""
    return _normalize_schema(_get_schema(tool), _GEMINI_TYPES)


def build_ollama_system_prompt_suffix(tool: Any) -> str:
    """Compose a system-prompt suffix that documents the tool for Ollama.

    Ollama's tool format is OpenAI-compatible, but for local models that
    consume the prompt directly (rather than the JSON tool-call field),
    a human-readable summary helps the model route the right tool.
    """
    name = _get_name(tool)
    desc = _get_description(tool)
    schema = _get_schema(tool)
    props = schema.get("properties", {}) if isinstance(schema, dict) else {}
    if not isinstance(props, dict):
        props = {}
    required = schema.get("required", []) if isinstance(schema, dict) else []

    lines = [f"Tool: {name}"]
    if desc:
        lines.append(f"Description: {desc}")
    if props:
        lines.append("Parameters:")
        for pname, pschema in props.items():
            if not isinstance(pschema, dict):
                continue
            ptype = pschema.get("type", "any")
            pdesc = pschema.get("description", "")
            req_marker = " (required)" if pname in required else ""
            line = f"  - {pname}: {ptype}{req_marker}"
            if pdesc:
                line += f" — {pdesc}"
            lines.append(line)
    return "\n".join(lines)