"""Harness #2 — provider adapters: openai, anthropic, gemini.

These three adapters are the most architecturally distinct in mcpschema:

- ``to_openai_tool`` wraps the function in ``{"type": "function", ...}``
  and uses the OpenAI lowercase type map.
- ``to_anthropic_tool`` uses ``getattr(tool, "name", "")`` directly
  (VULN_AUDIT finding H-1 flagged this as different from the OpenAI
  adapter's safer ``_get_name`` route).
- ``to_gemini_tool`` uppercases parameter types and conditionally
  omits the ``description`` key.

Plus, every adapter internally calls ``_normalize_schema`` /
``_normalize_property`` — so fuzzing the adapters covers the same
schema-normalization code as harness_tool.py, but from the OUTER edge
(every public adapter function, no internals exposed).

Method
------
For each input:

1. Parse JSON.
2. If it's a dict, treat it as a single tool payload and route through
   each of the three adapters via ``tool_from_dict``.
3. If it's a list, route every dict element through each adapter.
4. If it's neither, the adapters are still called against the raw
   payload (they're duck-typed on ``getattr``, so anything with the right
   attribute names works — and anything else should fail gracefully).

Documented exceptions
---------------------
- ``ValueError`` — invalid JSON or missing name in tool_from_dict.

Atheris's signal handler will surface any stack-overflow (from
``RecursionError``) or sanitized UBSan ASAN fault as a real bug.

Run
---
::

    python -m atheris harness_providers.py -atheris_runs=200000

Replay::

    python harness_providers.py path/to/crash.bin
"""

from __future__ import annotations

import sys
from typing import Any, Callable

from _shared import atheris_setup, replay_main, safe_call_json

from mcpschema import (  # noqa: E402
    to_anthropic_tool,
    to_gemini_tool,
    to_openai_tool,
    tool_from_dict,
)


_LABEL = "providers"

# All three adapters under test. Looping over them is the harness's
# whole point — we want each input to exercise every code path.
ADAPTERS: tuple[Callable[[Any], dict[str, Any]], ...] = (
    to_openai_tool,
    to_anthropic_tool,
    to_gemini_tool,
)


def _route_through_adapters(obj: Any) -> None:
    """Push ``obj`` through every adapter, swallowing documented behavior."""
    for adapter in ADAPTERS:
        # The adapter call is the actual unit under test. Anything not
        # ``ValueError`` is a real bug.
        adapter(obj)


def _test_one_input(data: bytes) -> None:
    """Run every adapter against a coerced interpretation of ``data``."""

    # 1. Direct path: raw JSON → tool_from_dict (when a dict) → adapters.
    try:
        payload = safe_call_json(data)
    except ValueError:
        payload = None

    if isinstance(payload, dict):
        # VULN_AUDIT H-1 noted this adapter family uses getattr(...,"")
        # routes. tool_from_dict raises ValueError on missing name; that
        # is the documented behavior. Everything else is fair game.
        try:
            tool = tool_from_dict(payload)
        except ValueError:
            tool = None
        if tool is not None:
            _route_through_adapters(tool)

    elif isinstance(payload, list):
        # List-of-tools path. We coerce each dict element through
        # tool_from_dict; non-dict elements are passed through verbatim
        # (mirroring the CLI's _normalize_tools behavior).
        for item in payload:
            if isinstance(item, dict):
                try:
                    tool = tool_from_dict(item)
                except ValueError:
                    continue
            else:
                tool = item
            _route_through_adapters(tool)

    else:
        # Neither dict nor list — exercise the duck-typed fallback path
        # so we hit the ``getattr(..., "")`` branches even when the
        # input is a string, int, None, etc.
        _route_through_adapters(payload)


def main() -> None:
    atheris_setup(_LABEL, _test_one_input)


def _replay() -> int:
    return replay_main(_LABEL, _test_one_input)


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] in {"--help", "-h"}:
        sys.stderr.write(__doc__)
        sys.exit(0)
    if len(sys.argv) == 2 and not sys.argv[1].startswith("-"):
        sys.exit(_replay())
    main()
