"""Collect the declared local-test command as mechanical evidence."""

from __future__ import annotations
from pathlib import Path
from lokay.proc.test_local import declared_test_argv


def collect(worktree: str) -> dict:
    argv = declared_test_argv(Path(worktree))
    return {
        "ok": True,
        "evidence_kind": "test_contract",
        "evidence": {"argv": list(argv) if argv else []},
    }
