"""``mcpschema`` CLI — convert MCP tool schemas to provider formats on the
command line.

Usage::

    $ mcpschema convert --provider openai --input '[{"name":"x","description":"y","inputSchema":{}}]'
    $ echo '[{"name":"x",...}]' | mcpschema convert --provider anthropic --input -
    $ mcpschema providers
    $ mcpschema --help
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Sequence

from mcpschema import PROVIDERS, __version__, convert, convert_all, tool_from_dict


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mcpschema",
        description=(
            "Convert MCP tool schemas to OpenAI, Anthropic, Gemini, Ollama, "
            "DeepSeek, and Mistral tool-call formats."
        ),
    )
    p.add_argument("--version", action="version", version=f"mcpschema {__version__}")
    sub = p.add_subparsers(dest="command")

    # providers
    sub.add_parser(
        "providers",
        help="List supported provider names and exit.",
    )

    # convert
    conv = sub.add_parser(
        "convert",
        help="Convert a JSON tool payload to a provider format.",
    )
    conv.add_argument(
        "--provider",
        required=True,
        choices=sorted(PROVIDERS.keys()),
        help="Target provider name (case-insensitive).",
    )
    conv.add_argument(
        "--input",
        required=True,
        help=(
            "JSON payload — either a single tool dict, a list of tool dicts, "
            "or '-' to read from stdin."
        ),
    )
    conv.add_argument(
        "--compact",
        action="store_true",
        help="Emit single-line JSON instead of pretty-printed.",
    )

    return p


def _read_input(value: str) -> Any:
    """Resolve the --input flag to a Python object."""
    if value == "-":
        raw = sys.stdin.read()
    else:
        raw = value
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"mcpschema: invalid JSON in --input: {exc}") from exc


def _normalize_tools(payload: Any) -> list[Any]:
    """Accept a single dict or a list of dicts; return a list of tool objects."""
    if isinstance(payload, dict):
        return [tool_from_dict(payload)]
    if isinstance(payload, list):
        return [tool_from_dict(item) if isinstance(item, dict) else item for item in payload]
    raise SystemExit(
        f"mcpschema: --input must be a JSON dict or list of dicts; got {type(payload).__name__}"
    )


def _cmd_convert(args: argparse.Namespace) -> int:
    payload = _read_input(args.input)
    is_single = isinstance(payload, dict)
    tools = _normalize_tools(payload)
    out = convert_all(tools, args.provider)
    # If the user supplied a single dict (not a list), emit a single dict.
    if is_single and len(out) == 1:
        result: Any = out[0]
    else:
        result = out
    if args.compact:
        print(json.dumps(result, separators=(",", ":"), ensure_ascii=False))
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _cmd_providers(_: argparse.Namespace) -> int:
    print(f"mcpschema {__version__} supports {len(PROVIDERS)} providers:")
    for name in sorted(PROVIDERS.keys()):
        print(f"  - {name}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "providers":
        return _cmd_providers(args)
    if args.command == "convert":
        return _cmd_convert(args)
    parser.print_help()
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())