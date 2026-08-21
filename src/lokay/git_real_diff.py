"""Classify a worktree diff: real progress vs plan/localize evidence only."""

from __future__ import annotations

from pathlib import Path

from lokay.approach_plan import APPROACH_REL_PATH
from lokay.localize import LOCALIZE_REL_PATH
from lokay.runner import Runner, git_spec

# Plan/localize evidence (and trivial lockstep of those two files).
EVIDENCE_PATHS = frozenset({APPROACH_REL_PATH, LOCALIZE_REL_PATH})
# uv.lock-only is not real uncommitted content.
_DISPOSABLE_TRACKED_NAMES = frozenset({"uv.lock"})


def normalize_rel(path: str) -> str:
    # Git's -z path output uses repository-relative '/' separators. A backslash
    # is a valid POSIX filename byte and must not alias plan evidence.
    text = path
    while text.startswith("./"):
        text = text[2:]
    return text


def is_evidence_path(path: str) -> bool:
    return normalize_rel(path) in EVIDENCE_PATHS


_DISPOSABLE_IGNORED_PARTS = frozenset(
    {".venv", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", ".uv"}
)
_DISPOSABLE_IGNORED_NAMES = frozenset({"dist", "build"})


def is_disposable_ignored_path(path: str) -> bool:
    """Artifacts that may be regenerated and are not implementation progress."""
    rel = normalize_rel(path)
    parts = tuple(part for part in rel.split("/") if part)
    return bool(parts) and (
        any(part in _DISPOSABLE_IGNORED_PARTS for part in parts)
        or parts[0] in _DISPOSABLE_IGNORED_NAMES
        or any(part.endswith(".egg-info") for part in parts)
        or parts[-1].endswith((".pyc", ".pyo"))
    )


def is_disposable_tracked_path(path: str) -> bool:
    """uv.lock-only is not real uncommitted content."""
    rel = normalize_rel(path)
    parts = tuple(part for part in rel.split("/") if part)
    return bool(parts) and parts[-1] in _DISPOSABLE_TRACKED_NAMES


def classify_changed_paths(paths: list[str] | tuple[str, ...]) -> str:
    """empty | plan_only | real."""
    cleaned = [normalize_rel(p) for p in paths if normalize_rel(p)]
    cleaned = [p for p in cleaned if not is_disposable_tracked_path(p)]
    if not cleaned:
        return "empty"
    if all(is_evidence_path(p) for p in cleaned):
        return "plan_only"
    return "real"


def _list_paths(runner: Runner, worktree: Path, queries: tuple[list[str], ...]) -> list[str]:
    found: set[str] = set()
    for argv in queries:
        result = runner.run(git_spec(argv, cwd=worktree), live=True)
        detail = (result.stderr or "").strip()
        if result.returncode != 0 or detail:
            detail = detail or (result.stdout or "").strip()
            raise RuntimeError(detail or f"cannot inspect worktree paths: {' '.join(argv)}")
        raw = result.stdout or ""
        records = raw.split("\0") if "\0" in raw else raw.splitlines()
        for line in records:
            rel = normalize_rel(line)
            if rel:
                found.add(rel)
    return sorted(found)


def list_uncommitted_paths(runner: Runner, worktree: Path) -> list[str]:
    """Union of staged, unstaged, and untracked paths, excluding commits.

    Ignored files are still user data. Only documented reproducible cache/build
    artifacts are disposable; every ignored query failure remains uncertainty.
    """
    found = _list_paths(
        runner,
        worktree,
        (
            ["diff", "--name-only", "--cached", "--relative", "-z"],
            ["diff", "--name-only", "--relative", "-z"],
            ["ls-files", "--others", "--exclude-standard", "-z"],
        ),
    )
    ignored = _list_paths(
        runner,
        worktree,
        (["ls-files", "--others", "--ignored", "--exclude-standard", "-z"],),
    )
    return sorted(
        set(found).union(
            path for path in ignored if not is_disposable_ignored_path(path)
        )
    )


def list_committed_paths(runner: Runner, worktree: Path, *, base: str) -> list[str]:
    """Committed path names in ``base...HEAD`` with NUL-safe identity."""
    result = runner.run_checked(
        git_spec(
            ["diff", "--name-only", "--relative", "-z", f"{base}...HEAD"],
            cwd=worktree,
            timeout_seconds=120,
        ),
        live=True,
    )
    detail = (getattr(result, "stderr", "") or "").strip()
    if detail:
        raise RuntimeError(detail)
    raw = result.stdout or ""
    records = raw.split("\0") if "\0" in raw else raw.splitlines()
    return sorted({normalize_rel(path) for path in records if normalize_rel(path)})


def list_changed_paths(runner: Runner, worktree: Path, *, base: str) -> list[str]:
    """Union of committed, staged, unstaged, and untracked paths vs *base*."""
    committed = _list_paths(
        runner,
        worktree,
        (
            ["diff", "--name-only", "--relative", "-z", f"{base}...HEAD"],
            ["diff", "--name-only", "--relative", "-z", base],
        ),
    )
    return sorted(set(committed).union(list_uncommitted_paths(runner, worktree)))
