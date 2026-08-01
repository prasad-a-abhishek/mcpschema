"""CLI tests — acceptance criteria #16, #17, #18.

Uses subprocess (NOT exec) so we exercise the real installed entry point.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys

import pytest


def _cli() -> list[str]:
    """Locate the ``mcpschema`` CLI.

    Prefers the installed entry point (resolves via PATH); falls back to
    ``python -m mcpschema`` for environments where the entry point is not
    installed yet.
    """
    if shutil.which("mcpschema"):
        return ["mcpschema"]
    return [sys.executable, "-m", "mcpschema"]


def _run(*args: str, input: str | None = None, timeout: float = 10.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        _cli() + list(args),
        capture_output=True,
        text=True,
        input=input,
        timeout=timeout,
        env={"PATH": "/root/.local/bin:/usr/local/bin:/usr/bin:/bin"},
    )


# --- AC #18: --help exits 0 ---------------------------------------------


def test_cli_help_flag() -> None:
    r = _run("--help")
    assert r.returncode == 0
    assert "usage" in r.stdout.lower() or "options" in r.stdout.lower()


def test_cli_help_short_flag() -> None:
    r = _run("-h")
    assert r.returncode == 0


# --- AC #17: providers command ------------------------------------------


def test_cli_list_providers() -> None:
    r = _run("providers")
    assert r.returncode == 0
    out = r.stdout
    for name in ("openai", "anthropic", "gemini", "ollama", "deepseek", "mistral"):
        assert name in out, f"provider {name!r} missing from `providers` output: {out!r}"


# --- AC #16: convert command with --provider and --input -----------------


def test_cli_convert_flag() -> None:
    payload = json.dumps(
        [
            {
                "name": "x",
                "description": "y",
                "inputSchema": {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]},
            }
        ]
    )
    r = _run("convert", "--provider", "openai", "--input", payload)
    assert r.returncode == 0, f"stderr={r.stderr!r}"
    parsed = json.loads(r.stdout)
    assert isinstance(parsed, list)
    assert parsed[0]["type"] == "function"
    assert parsed[0]["function"]["name"] == "x"


def test_cli_convert_single_dict_input() -> None:
    """A single dict (not wrapped in a list) is also accepted."""
    payload = json.dumps(
        {"name": "x", "description": "y", "inputSchema": {"type": "object", "properties": {}}}
    )
    r = _run("convert", "--provider", "anthropic", "--input", payload)
    assert r.returncode == 0, f"stderr={r.stderr!r}"
    parsed = json.loads(r.stdout)
    # Should be returned as a single dict, not wrapped in a list.
    assert isinstance(parsed, dict)
    assert parsed["name"] == "x"


def test_cli_convert_invalid_json_exits_nonzero() -> None:
    r = _run("convert", "--provider", "openai", "--input", "not json")
    assert r.returncode != 0


def test_cli_convert_unknown_provider_exits_nonzero() -> None:
    payload = json.dumps([{"name": "x", "description": "y", "inputSchema": {}}])
    r = _run("convert", "--provider", "bogus", "--input", payload)
    assert r.returncode != 0


def test_cli_convert_stdin() -> None:
    """--input - reads from stdin."""
    payload = json.dumps([{"name": "x", "description": "y", "inputSchema": {}}])
    r = _run("convert", "--provider", "openai", "--input", "-", input=payload)
    assert r.returncode == 0, f"stderr={r.stderr!r}"
    parsed = json.loads(r.stdout)
    assert parsed[0]["function"]["name"] == "x"


def test_cli_convert_output_is_pretty_printed() -> None:
    """By default output is pretty-printed for readability."""
    payload = json.dumps([{"name": "x", "description": "y", "inputSchema": {}}])
    r = _run("convert", "--provider", "openai", "--input", payload)
    assert "\n" in r.stdout  # pretty-printed
    assert " " in r.stdout    # indented


def test_cli_convert_compact_flag() -> None:
    """--compact emits single-line JSON."""
    payload = json.dumps([{"name": "x", "description": "y", "inputSchema": {}}])
    r = _run("convert", "--provider", "openai", "--input", payload, "--compact")
    assert r.returncode == 0
    assert "\n" not in r.stdout.strip()  # compact form


def test_cli_convert_all_providers() -> None:
    """`convert --provider X` works for every supported provider."""
    payload = json.dumps([{"name": "x", "description": "y", "inputSchema": {}}])
    for provider in ("openai", "anthropic", "gemini", "ollama", "deepseek", "mistral"):
        r = _run("convert", "--provider", provider, "--input", payload, "--compact")
        assert r.returncode == 0, f"provider {provider!r} failed: stderr={r.stderr!r}"
        json.loads(r.stdout)  # must be valid JSON