"""Restore exactly one classified set of protected residue paths."""

from pathlib import Path

from lokay.proc._common import runner
from lokay.runner import git_spec


def restore(evidence: dict, changed: dict, authorized: dict) -> dict:
    paths = list(authorized.get("restore_paths") or [])
    runner().run_checked(
        git_spec(
            [
                "restore",
                "--source",
                changed["base"],
                "--staged",
                "--worktree",
                "--",
                *paths,
            ],
            cwd=Path(evidence["worktree"]),
        ),
        live=True,
    )
    return {"ok": True, "route": "restored", "restored_paths": paths}
