"""Harness #3 — CLI ``convert`` entrypoint.

The CLI is a separate process boundary from the Python API. Any crash
in the CLI is a real-world bug — it gets surfaced when an operator
types ``mcpschema convert --provider X --input ...`` against an
untrusted JSON payload.

Method
------
We invoke the CLI as a subprocess via the ``python -m mcpschema``
entry point (the same one the published wheel registers). Each input
is fed through the full argparse + JSON-parse + convert + JSON-emit
pipeline.

The CLI's documented behaviors are:

- ``SystemExit(invalid JSON)`` — raised by ``_read_input`` on bad JSON.
- ``SystemExit(--input must be a JSON dict or list of dicts)`` — raised
  by ``_normalize_tools`` on a non-list non-dict payload.
- ``ValueError`` — propagated from ``tool_from_dict`` for missing name.
- ``ValueError`` — propagated from ``_resolve_provider`` for a bad
  provider. (The CLI guards against this via argparse ``choices=``,
  but if a future regression drops the guard, this catches it.)

Anything else (segfault, RecursionError, TypeError, etc.) is a real
bug and is dumped to ``crashes/``.

Why subprocess instead of importing ``mcpschema.cli.main``?
----------------------------------------------------------
Importing the CLI module would test the same Python code path as
harness_tool.py / harness_providers.py. Calling it as a subprocess
exercises:

- The ``__main__`` guard in ``mcpschema/__main__.py``.
- The actual ``python -m mcpschema`` interpreter invocation (PATH lookup,
  sys.argv parsing, exit codes).
- A second ASan-runtime startup — if the CLI process itself crashes
  with a sanitizer fault, Atheris (running in the parent) sees the
  non-zero exit code.

Run
---
::

    python -m atheris harness_cli.py -atheris_runs=200000

Replay::

    python harness_cli.py path/to/crash.bin
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from _shared import (
    INPUT_TIMEOUT_SECONDS,
    atheris_setup,
    dump_crash,
    replay_main,
)


_LABEL = "cli"

# All currently supported providers. Mirrors ``mcpschema.PROVIDERS``.
_PROVIDERS: tuple[str, ...] = (
    "openai",
    "anthropic",
    "gemini",
    "ollama",
    "deepseek",
    "mistral",
)

# Path to the project's src — used so we run `python -m mcpschema` against
# the live source tree, not an installed wheel.
_REPO_SRC = Path(__file__).resolve().parents[3] / "src"


def _run_cli(payload: bytes) -> None:
    """Run ``python -m mcpschema convert --provider <p> --input -`` against
    ``payload`` on stdin, for every provider. Any non-zero exit dumps the
    input and re-raises as a failed assertion so Atheris reports it.
    """
    # Use a pre-determined provider — we don't want to fuzz the provider
    # name here; that's covered by ``harness_providers.py`` and the
    # argparse choices guard. Rotating through the providers changes
    # only the output formatting, not the parse/normalization path.
    for provider in _PROVIDERS:
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "mcpschema",
                "convert",
                "--provider",
                provider,
                "--input",
                "-",
                "--compact",
            ],
            input=payload,
            capture_output=True,
            timeout=INPUT_TIMEOUT_SECONDS,
            cwd=str(_REPO_SRC.parent),
            env={
                # Force the interpreter to use the live source tree.
                "PYTHONPATH": str(_REPO_SRC),
                # Don't let the child disable sanitizers.
                "MCPSCHEMA_HARNESS_SAN": "1",
            },
            check=False,
        )
        if proc.returncode != 0:
            stderr = proc.stderr.decode("utf-8", errors="replace")
            # The CLI's documented "bad input" path is: argparse exits 2
            # for usage errors, and SystemExit-from-ValueError exits 1
            # with a Python traceback for malformed JSON or missing name.
            # These are NOT crashes — they're the contract.
            is_documented = (
                proc.returncode == 2  # argparse (usage error / bad choice)
                or (
                    proc.returncode == 1
                    and (
                        "ValueError" in stderr
                        or "JSONDecodeError" in stderr
                        or "invalid JSON" in stderr
                        or "--input must be a JSON dict" in stderr
                        or "must have a non-empty 'name'" in stderr
                    )
                )
            )
            if is_documented:
                continue
            # Anything else (exit 139=SIGSEGV, 134=SIGABRT/ASan, 137=SIGKILL
            # from timeout, 0 with garbage, or exit 1 with a non-ValueError
            # traceback) is a real bug.
            raise RuntimeError(
                f"CLI subprocess crashed (provider={provider}, "
                f"exit={proc.returncode}): {stderr.strip()[:500]}"
            )
        # Exit 0 — guard against nonsense output (e.g. --input `-` printed
        # an empty line and the CLI exited 0 without saying anything).
        if proc.stdout and not _looks_like_json(proc.stdout):
            raise RuntimeError(
                f"CLI exited 0 but produced non-JSON output "
                f"(provider={provider}): {proc.stdout[:200]!r}"
            )


def _looks_like_json(blob: bytes) -> bool:
    """Best-effort check that the CLI's stdout is valid JSON."""
    import json
    try:
        json.loads(blob)
        return True
    except (ValueError, UnicodeDecodeError):
        return False


def _test_one_input(data: bytes) -> None:
    """Push raw bytes through the CLI as a JSON payload on stdin."""
    _run_cli(data)


def main() -> None:
    atheris_setup(_LABEL, _test_one_input)


def _replay() -> int:
    if len(sys.argv) != 2:
        sys.stderr.write(f"usage: {sys.argv[0]} <crash.bin>\n")
        return 64
    data = Path(sys.argv[1]).read_bytes()
    try:
        _run_cli(data)
    except BaseException as exc:
        dump_crash(data, _LABEL, exc)
        return 2
    print("no crash — CLI handled the input gracefully")
    return 0


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] in {"--help", "-h"}:
        sys.stderr.write(__doc__)
        sys.exit(0)
    if len(sys.argv) == 2 and not sys.argv[1].startswith("-"):
        sys.exit(_replay())
    main()
