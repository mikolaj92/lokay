"""Mechanically derive changed pytest targets after one red full suite."""

from pathlib import Path
from lokay.proc._common import runner
from lokay.proc.test_local import _changed_pytest_argv


def derive(inspected: dict, selected: dict) -> dict:
    if selected.get("route") != "scope":
        return {"ok": True, "route": "none", "argv": []}
    try:
        argv = _changed_pytest_argv(
            runner(), Path(inspected["worktree"]), tuple(inspected["test_argv"])
        )
    except Exception as exc:
        return {"ok": True, "route": "error", "error": str(exc)}
    return {"ok": True, "route": "scope" if argv else "none", "argv": list(argv or [])}
