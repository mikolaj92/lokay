from __future__ import annotations

import fnmatch
import re
from pathlib import Path

from lokay.fix import _git
from lokay.scope import is_artifact

LOCKFILES = {"uv.lock": "pyproject.toml", "poetry.lock": "pyproject.toml",
             "package-lock.json": "package.json", "pnpm-lock.yaml": "package.json",
             "yarn.lock": "package.json"}


def merge_guard(worktree: Path, title: str, body: str | None) -> dict:
    _git(worktree, ["fetch", "origin", "main"])
    # NUL separators preserve paths with spaces, tabs, or newlines (including renames).
    fields = _git(worktree, ["diff", "--name-status", "-z", "origin/main...HEAD"]).split("\0")
    changes = {}
    index = 0
    while index < len(fields) and fields[index]:
        status, path = fields[index:index + 2]
        index += 2
        if status.startswith(("R", "C")):
            changes[path] = "D"
            path = fields[index]
            index += 1
        changes[path] = status
    wants_tests = re.search(r"\b(?:test\w*|regresj\w*|regression\w*|pokrycie\w*|coverage\w*)\b",
                            title + "\n" + (body or ""), re.IGNORECASE)
    removed = [path for path, status in changes.items() if status == "A" and not wants_tests
               and ("tests" in Path(path).parts[:-1] or any(
                   fnmatch.fnmatchcase(Path(path).name, pattern)
                   for pattern in ("test_*.py", "*_test.py", "*.test.*", "*.spec.*")))]
    artifacts = [path for path, status in changes.items() if status != "D" and is_artifact(path)]
    removed = sorted(set(removed) | set(artifacts))
    reset = [path for path in changes if path not in removed and Path(path).name in LOCKFILES
             and str(Path(path).with_name(LOCKFILES[Path(path).name])) not in changes]
    if removed or reset:
        if _git(worktree, ["status", "--porcelain"]):
            raise RuntimeError("merge guard requires a clean worktree")
        if removed:
            _git(worktree, ["rm", "-r", "--cached", "--", *removed])
            for path in removed:
                (worktree / path).unlink(missing_ok=True)
        for path in reset:
            if _git(worktree, ["ls-tree", "--name-only", "origin/main", "--", path]):
                _git(worktree, ["checkout", "origin/main", "--", path])
            elif changes[path] != "D":
                _git(worktree, ["rm", "--", path])
        message = ("lokay merge-guard: drop artifacts" if artifacts
                   else "lokay merge-guard: drop new tests / reset lockfiles")
        _git(worktree, ["commit", "-m", message])
    return {"removed": removed, "reset": reset}
