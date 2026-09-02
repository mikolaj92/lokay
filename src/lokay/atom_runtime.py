"""Neutral runtime port for one atom main invocation.

Organs and the Fala dispatcher both depend on this module. Neither imports
the other for hooks.
"""

from __future__ import annotations

import contextlib
import io
import json
from typing import Any

from lokay.git_commit import branch_ahead_of_upstream  # noqa: F401 — tests patch this


def run_atom_main(module_main, argv: list[str]) -> dict[str, Any]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = module_main(argv)
    lines = buf.getvalue().strip().splitlines()
    if not lines:
        return {"ok": False, "error": "empty atom stdout", "_exit": code}
    data = json.loads(lines[-1])
    data["_exit"] = code
    return data
