"""Classify a worktree diff: real progress vs plan/localize evidence only."""

from __future__ import annotations

from pathlib import Path

from lokay.approach_plan import APPROACH_REL_PATH
from lokay.localize import LOCALIZE_REL_PATH
from lokay.runner import Runner, git_spec

# Plan/localize evidence (and trivial lockstep of those two files).
EVIDENCE_PATHS = frozenset({APPROACH_REL_PATH, LOCALIZE_REL_PATH})


def normalize_rel(path: str) -> str:
    text = path.strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text


def is_evidence_path(path: str) -> bool:
    return normalize_rel(path) in EVIDENCE_PATHS


def classify_changed_paths(paths: list[str] | tuple[str, ...]) -> str:
    """empty | plan_only | real."""
    cleaned = [normalize_rel(p) for p in paths if normalize_rel(p)]
    if not cleaned:
        return "empty"
    if all(is_evidence_path(p) for p in cleaned):
        return "plan_only"
    return "real"


def list_changed_paths(runner: Runner, worktree: Path, *, base: str) -> list[str]:
    """Union of committed, staged, unstaged, and untracked paths vs *base*."""
    found: set[str] = set()
    queries = (
        ["diff", "--name-only", "--relative", f"{base}...HEAD"],
        ["diff", "--name-only", "--relative", base],
        ["diff", "--name-only", "--cached", "--relative"],
        ["diff", "--name-only", "--relative"],
        ["ls-files", "--others", "--exclude-standard"],
    )
    for argv in queries:
        result = runner.run(git_spec(argv, cwd=worktree), live=True)
        for line in (result.stdout or "").splitlines():
            rel = normalize_rel(line)
            if rel:
                found.add(rel)
    return sorted(found)
