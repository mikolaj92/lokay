"""Collect a bounded repository tree for one coding evidence round."""

from __future__ import annotations
from pathlib import Path


def collect(worktree: str) -> dict:
    root = Path(worktree)
    paths = []
    for p in sorted(root.iterdir()) if root.is_dir() else []:
        if p.name not in {".git", ".venv", "node_modules"}:
            paths.append(p.name + ("/" if p.is_dir() else ""))
    return {
        "ok": True,
        "evidence_kind": "repo_structure",
        "evidence": {"top_level": paths[:100]},
    }
