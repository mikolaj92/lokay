"""Collect one bounded current diff for the localized coding scope."""

from __future__ import annotations
from pathlib import Path
from lokay.proc._common import runner
from lokay.runner import CommandSpec


def collect(worktree: str) -> dict:
    p = Path(worktree)
    r = runner().run(
        CommandSpec(
            ("git", "diff", "--no-ext-diff", "--"), cwd=str(p), timeout_seconds=60
        ),
        live=True,
    )
    if r.returncode:
        return {"ok": False, "error": (r.stderr or "git diff failed")[-1000:]}
    return {
        "ok": True,
        "evidence_kind": "localized_diff",
        "evidence": {"diff": (r.stdout or "")[-12000:]},
    }
