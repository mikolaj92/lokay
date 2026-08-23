"""Remove one confirmed disposable recovery worktree."""

from pathlib import Path
from lokay.git_worktree import remove_worktree
from lokay.proc._common import runner


def remove(classified: dict) -> dict:
    out = remove_worktree(
        runner(),
        Path(classified["clone"]),
        Path(classified["worktree"]),
        managed_root=Path(classified["managed_root"]),
    )
    return {
        **classified,
        "ok": bool(out.get("ok")),
        "route": "removed" if out.get("ok") else "remove_failed",
        "error": (
            ""
            if out.get("ok")
            else f"self-repair worktree remove failed: {out.get('error') or 'still exists'}"
        ),
    }
