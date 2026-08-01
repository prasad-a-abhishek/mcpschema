"""Harness #1 — core API surface: ``tool_from_dict`` + ``_normalize_schema``.

This is the most fundamental surface in mcpschema: every adapter (OpenAI,
Anthropic, Gemini, Ollama, DeepSeek, Mistral) ultimately walks through
the same two code paths:

1. ``tool_from_dict(raw)`` — coerce a JSON-RPC tool dict into an
   ``MCPTool`` (or raise ``ValueError`` for malformed input).
2. ``_normalize_schema(schema, type_map)`` — normalize the
   ``inputSchema`` for a target provider's type system.

If either breaks on adversarial input, every adapter breaks. So this
harness fuzzes both surfaces across every realistic attack shape:

- Raw bytes → ``json.loads`` → ``tool_from_dict`` (covers the JSON-RPC
  tool payload path the CLI and the public API use).
- Raw bytes → ``json.loads`` → ``_normalize_property`` (covers the
  per-property path with the OpenAI type map).
- Raw bytes → ``json.loads`` → ``_normalize_schema`` (covers the whole
  inputSchema path with the Gemini type map, exercising the uppercase
  branch too).

Documented exceptions
---------------------
- ``json.JSONDecodeError`` (a ``ValueError`` subclass) — triggered by
  invalid JSON.
- ``ValueError`` — raised by ``tool_from_dict`` when ``name`` is missing
  or not a non-empty string.

Anything else (RecursionError, KeyError, AttributeError, TypeError
raised outside the JSON-decoder, etc.) is a real bug and gets dumped
to ``crashes/``.

Run
---
::

    python -m atheris harness_tool.py -atheris_runs=200000 \
        corpus_tool/  # optional seed corpus

Replay a saved crash::

    python harness_tool.py crashes/20260801T1234567890_tool_abcdef012345.bin
"""

from __future__ import annotations

import sys
from typing import Any

from _shared import atheris_setup, replay_main, safe_call_json

# Public API under test.
from mcpschema import tool_from_dict  # noqa: E402

# Internal helpers — _normalize_schema is the spine of every adapter.
# We test it directly because it's the function where prior F-1/F-3
# crashes lived (commit 25cfd7a). Atheris + ASan/UBSan will catch any
# regression.
from mcpschema._schema import (  # noqa: E402
    _GEMINI_TYPES,
    _OPENAI_TYPES,
    _normalize_property,
    _normalize_schema,
)


_LABEL = "tool"


def _test_one_input(data: bytes) -> None:
    """Run all three fuzz vectors against the raw bytes."""

    # Vector 1: JSON-RPC tool payload → tool_from_dict.
    # This is the most realistic attacker input — JSON-RPC payloads from
    # an untrusted MCP server arriving on the wire.
    try:
        payload = safe_call_json(data)
    except ValueError:
        # Documented: invalid JSON is fine.
        payload = None

    if isinstance(payload, dict):
        # Documented: ValueError on missing/empty name. Everything else
        # (TypeError, AttributeError, …) is a bug.
        try:
            tool_from_dict(payload)
        except ValueError:
            pass  # contract: missing name → ValueError

    # Vector 2: random JSON → _normalize_property with OpenAI types.
    # This is the fast inner path. Recursive calls live here when a
    # property's `items` or `properties` key is itself a dict.
    # _normalize_property is documented to handle non-dict input by
    # returning {"type": "string"}; any ValueError/TypeError from inside
    # it on its own inputs is a real bug.
    if isinstance(payload, dict):
        try:
            _normalize_property(payload, _OPENAI_TYPES)
        except ValueError:
            # Acceptable (e.g. unhashable nested types); re-raise as bug otherwise.
            pass

    # Vector 3: random JSON-shaped dict → _normalize_schema with Gemini
    # types. Exercises the uppercase branch and the `required` list path.
    if isinstance(payload, dict):
        try:
            _normalize_schema(payload, _GEMINI_TYPES)
        except ValueError:
            pass


def main() -> None:
    atheris_setup(_LABEL, _test_one_input)


def _replay() -> int:
    return replay_main(_LABEL, _test_one_input)


if __name__ == "__main__":
    # Atheris's Setup only intercepts sys.argv when launched as
    # `python -m atheris harness_tool.py`. In that mode, "main" is not
    # invoked — Atheris takes over. We detect the mode by checking if
    # `--help` or a path argument was supplied.
    if len(sys.argv) >= 2 and sys.argv[1] in {"--help", "-h"}:
        sys.stderr.write(__doc__)
        sys.exit(0)
    if len(sys.argv) == 2 and not sys.argv[1].startswith("-"):
        sys.exit(_replay())
    main()
