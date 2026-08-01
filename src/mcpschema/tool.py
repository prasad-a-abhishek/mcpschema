"""``MCPTool`` dataclass and ``tool_from_dict`` helper.

The library is duck-typed: any object exposing ``name``, ``description``,
and ``inputSchema`` works as input. ``MCPTool`` is offered as a concrete
type for callers that want one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MCPTool:
    """Minimal concrete type for an MCP-style tool.

    Attributes:
        name: Tool name (matches MCP's ``Tool.name``).
        description: Human-readable description (may be empty string).
        inputSchema: JSON-Schema-shaped dict describing parameters.
    """

    name: str
    description: str = ""
    inputSchema: dict[str, Any] = field(default_factory=dict)


def tool_from_dict(raw: dict[str, Any]) -> MCPTool:
    """Build an ``MCPTool`` from a JSON-RPC tool payload (or any compatible dict).

    Required key: ``name``. Optional: ``description``, ``inputSchema``.
    """
    name = raw.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError(f"tool dict must have a non-empty 'name' string; got {name!r}")
    return MCPTool(
        name=name,
        description=str(raw.get("description", "") or ""),
        inputSchema=dict(raw.get("inputSchema") or {}),
    )