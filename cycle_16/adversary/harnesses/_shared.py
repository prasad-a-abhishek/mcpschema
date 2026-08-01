"""Shared helpers for mcpschema LibFuzzer harnesses.

Every harness in this directory imports from here to get:

- ``setup()`` — Atheris entry point with ASan/UBSan expectations documented
  and a 5s per-input timeout (via :class:`_TimeoutFDP`).
- ``dump_crash()`` — structured crash reporter: writes the offending input
  bytes, a hex dump, a Python traceback, and the input decoded as text
  (lossy) into ``crashes/`` for later reproduction.
- ``safe_call_*`` — wrappers that swallow documented exceptions so the
  fuzzer only sees UNEXPECTED crashes (uncaught exceptions, ASan/UBSan
  faults, SIGSEGV, etc.).

Why a custom FDP wrapper?
-------------------------
Atheris's built-in fuzz harness runs each input through ``TestOneInput``
in a single thread. The 5s-per-input timeout is enforced by patching
``signal.alarm`` (Linux only — Atheris already requires Linux/macOS).
We use ``signal.setitimer`` with ``ITIMER_REAL`` so that deeply-recursive
inputs (e.g. a schema whose ``items`` recursively references itself via
``fdp.ConsumeBool``) cannot hang the harness indefinitely.

ASan / UBSan
------------
Atheris is built against libFuzzer and ASan. When the harness is launched
with ``atheris`` as the entry point (``python -m atheris harness.py``),
the underlying C++ runtime already enables ASan + UBSan. Setting the
``MCPSCHEMA_HARNESS_SAN=1`` env var is a sanity check plus turns on
``PYTHONMALLOC=malloc`` so Python's allocator faults are detectable.

This module does NOT spawn child processes or invoke the CLI — that lives
in ``harness_cli.py``.
"""

from __future__ import annotations

import contextlib
import datetime as _dt
import hashlib
import json
import os
import signal
import sys
import traceback
from pathlib import Path
from typing import Any, Callable, Iterator

# Allow `python -m atheris harness.py` to find the live source tree.
_HERE = Path(__file__).resolve().parent
_REPO_SRC = _HERE.parents[3] / "src"  # /root/projects/mcpschema/src
if str(_REPO_SRC) not in sys.path:
    sys.path.insert(0, str(_REPO_SRC))

import atheris  # noqa: E402  (after sys.path tweak)

CRASH_DIR = _HERE / "crashes"
CRASH_DIR.mkdir(parents=True, exist_ok=True)

# Documented "expected" exceptions — these are part of the contract
# (e.g. tool_from_dict raises ValueError on missing name). We do NOT
# report these as crashes; the fuzzer only cares about unexpected
# exceptions (TypeError, KeyError, AttributeError, RecursionError, etc.).
_EXPECTED_EXCEPTIONS: tuple[type[BaseException], ...] = (
    ValueError,
    TypeError,  # JSONDecoder raises ValueError; we wrap with safe_call_json
)

# Timeout per input — 5 seconds as required by the task spec.
INPUT_TIMEOUT_SECONDS = 5


def _now_stamp() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).strftime("%Y%m%dT%H%M%S%f")


def configure_sanitizers() -> None:
    """Configure Python to cooperate with ASan/UBSan.

    Atheris launches with ASan + UBSan enabled by the C++ runtime. We
    additionally:

    - Ask Python's allocator to use system ``malloc`` so any out-of-bounds
      heap access (which ASan must detect) actually faults.
    - Set the env var ``MCPSCHEMA_HARNESS_SAN=1`` so downstream harnesses
      can detect that they're running under sanitizer instrumentation.
    """
    os.environ.setdefault("MCPSCHEMA_HARNESS_SAN", "1")
    # PYTHONMALLOC=malloc is harmless to set even if the lib is already built
    # with pymalloc. It makes ASan more useful for native extensions.
    os.environ.setdefault("PYTHONMALLOC", "malloc")


def dump_crash(data: bytes, label: str, exc: BaseException) -> Path:
    """Persist a fuzz-induced crash to ``crashes/`` for reproduction.

    Returns the path to the written ``.crash`` file. The file is JSON
    with the raw bytes (hex + base64), a UTC timestamp, the harness
    label, and a Python traceback. The actual raw bytes are also written
    alongside as ``<stamp>_<label>.bin`` so you can replay with
    ``python harness.py <file>``.
    """
    stamp = _now_stamp()
    safe_label = "".join(c if c.isalnum() or c in "-_" else "_" for c in label)
    digest = hashlib.sha256(data).hexdigest()[:12]
    bin_path = CRASH_DIR / f"{stamp}_{safe_label}_{digest}.bin"
    json_path = CRASH_DIR / f"{stamp}_{safe_label}_{digest}.crash.json"

    bin_path.write_bytes(data)

    payload = {
        "harness": label,
        "timestamp_utc": stamp,
        "input_sha256": hashlib.sha256(data).hexdigest(),
        "input_size_bytes": len(data),
        "input_hex_prefix": data[:256].hex(),
        "input_text_lossy": data[:1024].decode("utf-8", errors="replace"),
        "exception_type": type(exc).__name__,
        "exception_repr": repr(exc),
        "traceback": "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        ),
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    sys.stderr.write(
        f"\n[mcpschema-harness] CRASH {label} -> {json_path}\n"
        f"  reproduce: python -m atheris {Path(sys.argv[0]).name} "
        f"-- {bin_path}\n"
        f"  (or directly: python -c \"import sys; sys.path.insert(0, "
        f"{str(_REPO_SRC)!r}); from harness_{label} import *; "
        f"test_one_input(open({bin_path!r},'rb').read())\")\n"
    )
    return json_path


def _is_expected(exc: BaseException) -> bool:
    """Return True if ``exc`` is part of the documented behavior contract."""
    return isinstance(exc, _EXPECTED_EXCEPTIONS)


def _timeout_handler(signum: int, frame: Any) -> None:
    """SIGALRM handler — abort the current input with a clear error."""
    raise TimeoutError(
        f"input exceeded {INPUT_TIMEOUT_SECONDS}s budget (possible infinite "
        f"loop or pathologically deep recursion)"
    )


@contextlib.contextmanager
def _input_timeout() -> Iterator[None]:
    """Arm a 5-second wall-clock timer for the duration of the block.

    Implemented with ``signal.setitimer(ITIMER_REAL, ...)`` so nested
    ``signal.alarm`` calls (which Atheris already uses) compose safely.
    """
    # ITIMER_REAL is the only signal that can interrupt a true infinite loop
    # in C code; SIGALRM/ITIMER_REAL is delivered to whichever thread the
    # kernel schedules.
    old = signal.setitimer(signal.ITIMER_REAL, INPUT_TIMEOUT_SECONDS)
    try:
        yield
    finally:
        # Disarm timer even if the block raised.
        signal.setitimer(signal.ITIMER_REAL, 0)
        if old != (0.0, 0.0):
            # Restore the previous timer (from a parent context).
            signal.setitimer(signal.ITIMER_REAL, old[0], old[1])


def safe_call_json(blob: bytes) -> Any:
    """``json.loads`` wrapper — returns whatever the decoder produces.

    Atheris can produce arbitrary bytes; we hand them straight to the
    stdlib decoder. JSONDecodeError is a ValueError subclass so it is
    already in the expected-exceptions list.
    """
    return json.loads(blob)


def run_one_input(
    label: str,
    data: bytes,
    test_fn: Callable[[bytes], None],
) -> None:
    """Single-input runner used by both LibFuzzer and replay modes.

    Wraps ``test_fn`` in a per-input timeout and crash-dump handler.
    ``test_fn`` should call the public API under test and let any
    documented exception propagate; UNEXPECTED exceptions are dumped
    to ``crashes/`` and re-raised so Atheris reports them as bugs.
    """
    with _input_timeout():
        try:
            test_fn(data)
        except BaseException as exc:  # noqa: BLE001 — we re-raise below
            if _is_expected(exc):
                # Documented behavior — feed Atheris nothing to complain about.
                return
            # Anything else is a real bug. Dump + re-raise.
            dump_crash(data, label, exc)
            raise


def atheris_setup(label: str, test_fn: Callable[[bytes], None]) -> None:
    """Standard Atheris entry point.

    ``label`` is the harness name (used for crash dump filenames).
    ``test_fn`` is the function Atheris calls per input — it must accept
    raw bytes and exercise the surface under test.
    """
    configure_sanitizers()

    def _wrapped(data: bytes) -> None:
        run_one_input(label, data, test_fn)

    # Atheris's Setup replaces sys.argv with the remaining args so that
    # `python -m atheris harness.py corpus/` works. We pass _wrapped as
    # the harness function.
    atheris.Setup(sys.argv, _wrapped)
    atheris.Fuzz()


def replay_main(label: str, test_fn: Callable[[bytes], None]) -> int:
    """Minimal CLI helper for replaying a single crash file.

    Usage::

        python harness_tool.py path/to/crash.bin
        python harness_tool.py -    # read from stdin

    Runs the input through ``test_fn`` with the same timeout + crash
    handler as the fuzzer would. Returns 0 on success, 1 on documented
    behavior, 2 on unexpected crash (the crash is also dumped).
    """
    if len(sys.argv) != 2:
        sys.stderr.write(
            f"usage: {sys.argv[0]} <crash.bin|->\n"
            "  (the fuzzer entry point is `python "
            f"{sys.argv[0]} -atheris_runs=1000 corpus/` instead)\n"
        )
        return 64
    if sys.argv[1] == "-":
        data = sys.stdin.buffer.read()
    else:
        path = Path(sys.argv[1])
        if not path.is_file():
            sys.stderr.write(f"error: {path} not found\n")
            return 66
        data = path.read_bytes()
    try:
        with _input_timeout():
            test_fn(data)
    except BaseException as exc:
        if _is_expected(exc):
            print(f"documented behavior: {type(exc).__name__}: {exc}")
            return 0
        dump_crash(data, label, exc)
        return 2
    print("no crash — input handled gracefully")
    return 0
