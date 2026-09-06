"""Done-means version stamp paths — always committed, never left dirty vs HEAD."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

# Basenames that product Done-means / check_stamps typically touch.
# Keep small and mechanical — not an LLM judgment.
STAMP_BASENAMES = frozenset(
    {
        "README.md",
        "CHANGELOG.md",
        "pyproject.toml",
        "pixi.toml",
        "uv.lock",
        "Cargo.toml",
        "Cargo.lock",
        "package.json",
        "package-lock.json",
        "mise.toml",
        "check_stamps.py",
    }
)


def is_stamp_rel(rel: str) -> bool:
    name = PurePosixPath(rel.removeprefix("./")).name
    return name in STAMP_BASENAMES


def dirty_paths(worktree: Path, *, porcelain: str) -> list[str]:
    """Parse `git status --porcelain -u` into repo-relative paths (dirty only)."""
    out: list[str] = []
    for line in porcelain.splitlines():
        if len(line) < 4:
            continue
        # XY PATH or XY ORIG -> PATH
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        path = path.strip().strip('"')
        if path and path not in out:
            out.append(path)
    return out


def dirty_stamp_paths(worktree: Path, *, porcelain: str) -> list[str]:
    return [p for p in dirty_paths(worktree, porcelain=porcelain) if is_stamp_rel(p)]
