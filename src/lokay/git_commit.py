from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path, PurePosixPath

from lokay.runner import Runner, git_spec


_EVIDENCE_PATHS = {".lokay/approach.md", ".lokay/localize.json"}


def _localized_paths(worktree: Path) -> list[str] | None:
    path = worktree / ".lokay" / "localize.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(".lokay/localize.json must contain an object")
    raw_paths = payload.get("paths", [])
    if not isinstance(raw_paths, list) or not all(isinstance(item, str) for item in raw_paths):
        raise ValueError(".lokay/localize.json paths must be a list of strings")

    paths: list[str] = []
    for raw in raw_paths:
        rel = raw.removeprefix("./").rstrip("/")
        pure = PurePosixPath(rel)
        if not rel or pure.is_absolute() or ".." in pure.parts or "\0" in rel:
            raise ValueError(f"invalid localized path: {raw!r}")
        if rel not in _EVIDENCE_PATHS and rel not in paths:
            paths.append(rel)
    return paths


def _literal_pathspecs(paths: list[str]) -> list[str]:
    return [f":(literal){path}" for path in paths]


def worktree_has_diff(runner: Runner, worktree: Path, *, live: bool) -> bool:
    if not live:
        return False
    staged = runner.run(git_spec(["diff", "--cached", "--quiet"], cwd=worktree), live=True)
    unstaged = runner.run(git_spec(["diff", "--quiet"], cwd=worktree), live=True)
    untracked = runner.run(
        git_spec(["ls-files", "--others", "--exclude-standard"], cwd=worktree),
        live=True,
    )
    return staged.returncode != 0 or unstaged.returncode != 0 or bool((untracked.stdout or "").strip())


def branch_ahead_of_main(
    runner: Runner, worktree: Path, *, live: bool, base: str = "main"
) -> int:
    if not live:
        return 0
    ahead = runner.run(
        git_spec(["rev-list", "--count", f"origin/{base}..HEAD"], cwd=worktree),
        live=True,
    )
    try:
        return int((ahead.stdout or "0").strip() or "0")
    except ValueError:
        return 0


def branch_ahead_of_upstream(runner: Runner, worktree: Path, *, live: bool) -> int:
    if not live:
        return 0
    ahead = runner.run(
        git_spec(["rev-list", "--count", "@{upstream}..HEAD"], cwd=worktree),
        live=True,
    )
    if ahead.returncode != 0:
        return 0
    try:
        return int((ahead.stdout or "0").strip() or "0")
    except ValueError:
        return 0


def _is_protected_main_checkout(
    runner: Runner,
    worktree: Path,
    protected_checkouts: Iterable[Path],
) -> bool:
    """Whether this is a configured host checkout currently on ``main``."""
    resolved = worktree.resolve()
    if not any(resolved == Path(checkout).resolve() for checkout in protected_checkouts):
        return False
    branch = runner.run(
        git_spec(["symbolic-ref", "--quiet", "--short", "HEAD"], cwd=resolved),
        live=True,
    )
    return branch.returncode == 0 and (branch.stdout or "").strip() == "main"


def commit_all(
    runner: Runner,
    worktree: Path,
    message: str,
    *,
    live: bool,
    protected_checkouts: Iterable[Path] = (),
) -> bool:
    if not live or _is_protected_main_checkout(runner, worktree, protected_checkouts):
        return False

    localized = _localized_paths(worktree)
    if localized is not None:
        tracked = runner.run_checked(
            git_spec(["ls-files", "-z"], cwd=worktree), live=True
        ).stdout.split("\0")
        actionable = [
            rel
            for rel in localized
            if (worktree / rel).exists()
            or any(path == rel or path.startswith(f"{rel}/") for path in tracked)
        ]
        if not actionable:
            return False
        pathspecs = _literal_pathspecs(actionable)
        runner.run_checked(
            git_spec(["add", "-A", "--", *pathspecs], cwd=worktree), live=True
        )
        status = runner.run(
            git_spec(["diff", "--cached", "--quiet", "--", *pathspecs], cwd=worktree),
            live=True,
        )
        if status.returncode == 0:
            return False
        # --only prevents an already-staged off-goal file (or plan evidence)
        # from hitching a ride in this commit.
        runner.run_checked(
            git_spec(["commit", "--only", "-m", message, "--", *pathspecs], cwd=worktree),
            live=True,
        )
        return True

    runner.run_checked(git_spec(["add", "-A"], cwd=worktree), live=True)
    # Legacy runs without localization still keep their plan evidence.
    for rel in _EVIDENCE_PATHS:
        if (worktree / rel).is_file():
            runner.run_checked(
                git_spec(["add", "-f", "--", rel], cwd=worktree),
                live=True,
            )
    status = runner.run(git_spec(["diff", "--cached", "--quiet"], cwd=worktree), live=True)
    if status.returncode == 0:
        return False
    runner.run_checked(git_spec(["commit", "-m", message], cwd=worktree), live=True)
    return True
