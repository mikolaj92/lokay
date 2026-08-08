"""Shared helpers: run atomic mains and optional Fala paths.

Default engine is **Unix atomics**. Fala is an explicit opt-in (`LOKAY_USE_FALA=1`),
not a silent fallback. When Fala is requested, failures must surface — do not
fall through to atoms (docs/FALLBACKS.md).
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable


def use_fala() -> bool:
    return os.environ.get("LOKAY_USE_FALA", "").strip().lower() in {"1", "true", "yes", "on"}


def run_atom(main_fn: Callable[..., int], argv: list[str]) -> dict[str, Any]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = main_fn(argv)
    lines = buf.getvalue().strip().splitlines()
    if not lines:
        return {"ok": False, "error": "empty process output", "_exit": code}
    data = json.loads(lines[-1])
    data["_exit"] = code
    return data


def write_temp(text: str, *, suffix: str = ".md") -> str:
    with tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False, encoding="utf-8") as fh:
        fh.write(text)
        return fh.name


def unlink_quiet(path: str | None) -> None:
    if not path:
        return
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass
