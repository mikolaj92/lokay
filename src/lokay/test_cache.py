"""Content-addressed receipt for an unchanged repository verifier run."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from lokay.runner import CommandSpec, Runner


def git_sha(run: Runner, worktree: Path, ref: str) -> str | None:
    result = run.run(CommandSpec(("git", "rev-parse", ref), cwd=str(worktree)), live=True)
    if result.returncode != 0:
        return None
    value = (result.stdout or "").strip()
    return value or None


def cache_key(run: Runner, worktree: Path, test_argv: tuple[str, ...]) -> str | None:
    if not (worktree / ".git").exists():
        return None
    head = git_sha(run, worktree, "HEAD")
    base = git_sha(run, worktree, "origin/main")
    if not head or not base:
        return None
    blob = json.dumps({"head": head, "base": base, "test": test_argv}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


def cache_path(worktree: Path) -> Path:
    dotgit = worktree / ".git"
    if dotgit.is_dir():
        gitdir = dotgit
    else:
        try:
            marker = dotgit.read_text(encoding="utf-8").strip()
        except OSError:
            marker = ""
        if not marker.startswith("gitdir:"):
            return worktree / ".lokay-test-local.json"
        gitdir = Path(marker.split(":", 1)[1].strip())
        if not gitdir.is_absolute():
            gitdir = (worktree / gitdir).resolve()
    return gitdir / "lokay-test-local.json"


def read_green(worktree: Path, key: str | None) -> dict[str, Any] | None:
    if key is None:
        return None
    path = cache_path(worktree)
    try:
        row = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return row if row.get("key") == key and row.get("passed") is True else None


def write_green(worktree: Path, key: str | None, tests: str) -> None:
    if key is None:
        return
    path = cache_path(worktree)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=".lokay-test-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump({"key": key, "passed": True, "tests": tests}, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(raw, path)
    finally:
        try:
            os.unlink(raw)
        except FileNotFoundError:
            pass
