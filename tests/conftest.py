"""Shared fixtures and helpers for the mcpschema test suite."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest


@dataclass(frozen=True)
class FakeTool:
    """Duck-typed stand-in for ``mcp.types.Tool``.

    The library must accept any object exposing ``name``, ``description``,
    and ``inputSchema`` — it does NOT require the MCP Python SDK.
    """

    name: str
    description: str = ""
    inputSchema: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class _DictShim:
    """Object exposing the three attrs but built from a dict.

    Used to assert duck-typing of MCP server tool objects that may not be
    a ``dataclass`` instance.
    """

    name: str
    description: str
    inputSchema: dict[str, Any]


def make_tool(name: str, description: str = "", inputSchema: dict[str, Any] | None = None) -> FakeTool:
    """Helper to build a FakeTool with a default empty schema."""
    return FakeTool(name=name, description=description, inputSchema=inputSchema or {})


def make_dict_tool(name: str, description: str, inputSchema: dict[str, Any]) -> _DictShim:
    """Build a tool shim from a dict (matches MCP JSON-RPC tool payloads)."""
    return _DictShim(name=name, description=description, inputSchema=inputSchema)


@pytest.fixture
def basic_tool() -> FakeTool:
    """A minimal tool with one integer parameter — used by many tests."""
    return FakeTool(
        name="git_log",
        description="Get recent commits",
        inputSchema={
            "type": "object",
            "properties": {
                "n": {"type": "integer", "default": 10, "description": "Number of commits"},
            },
            "required": ["n"],
        },
    )


@pytest.fixture
def empty_tool() -> FakeTool:
    """Tool with no parameters at all."""
    return FakeTool(name="ping", description="Health check", inputSchema={})


@pytest.fixture
def nested_tool() -> FakeTool:
    """Tool with a nested-object parameter — used for Anthropic/Gemini nesting tests."""
    return FakeTool(
        name="search",
        description="Search items",
        inputSchema={
            "type": "object",
            "properties": {
                "filter": {
                    "type": "object",
                    "properties": {
                        "tag": {"type": "string"},
                        "limit": {"type": "integer", "default": 25},
                    },
                    "required": ["tag"],
                }
            },
            "required": ["filter"],
        },
    )


@pytest.fixture
def array_tool() -> FakeTool:
    """Tool with an array-typed parameter — used for AC #20."""
    return FakeTool(
        name="tag_items",
        description="Apply tags to items",
        inputSchema={
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of item IDs",
                }
            },
            "required": ["items"],
        },
    )


@pytest.fixture
def boolean_tool() -> FakeTool:
    """Tool with a boolean parameter — used for AC #21."""
    return FakeTool(
        name="set_flag",
        description="Toggle a feature flag",
        inputSchema={
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean", "description": "Whether to enable"},
            },
            "required": ["enabled"],
        },
    )


@pytest.fixture
def deeply_nested_tool() -> FakeTool:
    """Three-level nested object — AC #22."""
    return FakeTool(
        name="deep_config",
        description="Apply deep configuration",
        inputSchema={
            "type": "object",
            "properties": {
                "level1": {
                    "type": "object",
                    "properties": {
                        "level2": {
                            "type": "object",
                            "properties": {
                                "level3": {
                                    "type": "string",
                                    "description": "Innermost leaf value",
                                }
                            },
                            "required": ["level3"],
                        }
                    },
                    "required": ["level2"],
                }
            },
            "required": ["level1"],
        },
    )