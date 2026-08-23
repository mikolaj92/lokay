"""List bounded untracked paths for explicit whitespace checks."""

from pathlib import Path
from lokay.proc._common import runner
from lokay.runner import git_spec


def list_paths(tested: dict, *, slot_count: int) -> dict:
    out = runner().run(
        git_spec(
            ["ls-files", "--others", "--exclude-standard", "-z"],
            cwd=Path(tested["worktree"]),
            timeout_seconds=120,
        ),
        live=True,
    )
    if out.returncode != 0:
        return {
            **tested,
            "ok": False,
            "error": "self-repair untracked diff check failed",
        }
    paths = [x for x in (out.stdout or "").split("\0") if x]
    if len(paths) > slot_count:
        return {
            **tested,
            "ok": False,
            "error": "self-repair untracked paths exceed authored slots",
            "paths": len(paths),
            "slot_count": slot_count,
        }
    return {**tested, "ok": True, "route": "paths", "paths": paths}
