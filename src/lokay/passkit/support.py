"""Shared helpers for factory-pass atoms (process I/O, not fleet policy)."""

from __future__ import annotations

import contextlib
import io
import json
from typing import Any, Callable


def is_manual_pr(pr: dict[str, Any]) -> bool:
    """Only an explicit, well-formed terminal label removes PR backpressure."""
    labels = pr.get("labels")
    return isinstance(labels, list) and all(isinstance(x, str) for x in labels) and (
        "ai:needs-review" in labels
    )


def run_proc(main_fn: Callable[..., int], argv: list[str]) -> dict[str, Any]:
    """Run one atom main, capture the last JSON envelope on stdout."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = main_fn(argv)
    lines = buf.getvalue().strip().splitlines()
    if not lines:
        return {"ok": False, "error": "empty process output", "_exit": code}
    data = json.loads(lines[-1])
    data["_exit"] = code
    return data


def run_select(main_fn: Callable[..., int], payload: dict[str, Any]) -> dict[str, Any]:
    """Run select_issue-style stdin JSON → stdout JSON."""
    import sys

    buf_in = json.dumps(payload)
    buf_out = io.StringIO()
    old_stdin = sys.stdin
    try:
        sys.stdin = io.StringIO(buf_in)
        with contextlib.redirect_stdout(buf_out):
            code = main_fn([])
    finally:
        sys.stdin = old_stdin
    data = json.loads(buf_out.getvalue().strip().splitlines()[-1])
    data["_exit"] = code
    return data
