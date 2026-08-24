"""Read one physical changed-path set against its base."""

from pathlib import Path

from lokay.git_real_diff import list_changed_paths
from lokay.proc._common import runner


def read(worktree: dict, *, base: str) -> dict:
    if worktree.get("route") != "read":
        return {"ok": True, "route": "unused", "paths": [], "base": base}
    try:
        paths = list_changed_paths(runner(), Path(worktree["worktree"]), base=base)
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": True,
            "route": "terminal",
            "reason": "diff_failed",
            "error": str(exc),
            "paths": [],
            "base": base,
        }
    return {"ok": True, "route": "classify", "paths": paths, "base": base}
