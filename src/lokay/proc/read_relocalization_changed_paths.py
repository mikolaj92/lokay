"""Read one physical changed-path set against the configured base."""

from pathlib import Path

from lokay.git_real_diff import list_changed_paths
from lokay.proc._common import runner


def read(evidence: dict, *, base: str) -> dict:
    if evidence.get("route") != "read":
        return {"ok": True, "route": "unused", "changed": []}
    try:
        paths = list_changed_paths(runner(), Path(evidence["worktree"]), base=base)
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": True,
            "route": "terminal",
            "reason": "diff_failed",
            "error": str(exc),
            "changed": [],
        }
    return {"ok": True, "route": "classify", "changed": paths, "base": base}
