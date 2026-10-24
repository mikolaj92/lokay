from __future__ import annotations

import fnmatch
import re
from collections.abc import Sequence
from pathlib import Path, PurePosixPath


ASSERTION = re.compile(
    r"^\s*(?:assert\s+|(?:[A-Za-z_]\w*\.)*(?:assert|assert[A-Z_]\w*|expect|XCTAssert\w*|#expect|_check|require)\s*\()"
)


CACHE_PATTERNS = [
    ".cache/", ".build/", "DerivedData/", "node_modules/", "__pycache__/",
    ".pytest_cache/", ".ruff_cache/", ".mypy_cache/", ".venv/", ".check-local/", ".local-checks/",
    "*.pyc", "*.db-shm", "*.db-wal", "manifest.db",
]


def kind(files: Sequence[object]) -> str:
    return "docs" if files and all(
        isinstance(path, str) and bool(path)
        and not Path(path).is_absolute() and ".." not in Path(path).parts
        and (path.startswith("docs/") or Path(path).suffix in {".md", ".rst", ".txt"})
        for path in files
    ) else "code"


def is_cache(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return any(fnmatch.fnmatchcase(part, pattern.rstrip("/"))
               for part in parts for pattern in CACHE_PATTERNS)


def is_junk(path: str, worktree: Path | None = None) -> bool:
    if worktree is None:
        return False
    relative = PurePosixPath(path)
    if relative.is_absolute() or ".." in relative.parts:
        return False
    for parent in relative.parents:
        if parent == PurePosixPath("."):
            continue
        directory = worktree / parent
        if ((directory / "CACHEDIR.TAG").is_file()
                or (directory / "conda-meta").is_dir()
                or (directory / "pyvenv.cfg").is_file()
                or (directory.name == "pkgs" and directory.is_dir()
                    and any((entry / "info/index.json").is_file() for entry in directory.iterdir()))):
            return True
    return False


def is_artifact(path: str, worktree: Path | None = None) -> bool:
    parts = PurePosixPath(path).parts
    name = PurePosixPath(path).name
    return (is_cache(path) or is_junk(path, worktree) or path.endswith(("/", ".log", ".sqlite", ".sqlite-shm", ".sqlite-wal"))
            or any(part == "git-v0" or part.endswith("uv-cache") for part in parts)
            or (worktree is not None and ((worktree / path).is_dir()
                or any((worktree / parent / ".git").exists()
                       or ((worktree / parent / "HEAD").is_file()
                           and (worktree / parent / "objects").is_dir())
                       for parent in (PurePosixPath(path), *PurePosixPath(path).parents)
                       if parent != PurePosixPath("."))))
            or ".local" in parts[:-1]
            or (len(parts) > 1 and parts[0].startswith(".tmp"))
            or any(fnmatch.fnmatchcase(name, pattern) for pattern in ("procs-*.json", "uv-*.lock"))
            or (worktree is not None and name.endswith(".lock")
                and (worktree / path).is_file() and (worktree / path).stat().st_size == 0)
            or any(part in {".validation", ".sandbox", "sandbox"} for part in parts[:-1])
            or (path.startswith("tmp/") and path.endswith(".lock"))
            or parts[-2:] == ("bin", "gh"))


def is_test(path: str, added_lines: Sequence[str] = ()) -> bool:
    parts = tuple(part.lower() for part in PurePosixPath(path).parts[:-1])
    name = PurePosixPath(path).name
    return ("tests" in parts
            or any(part in {"test", "spec", "specs", "smoke", "e2e", "__tests__", "testing", "integration_tests"}
                   for part in parts)
            or any(fnmatch.fnmatchcase(name, pattern) for pattern in
                   ("test_*.*", "*_test.*", "*.test.*", "*.spec.*", "*Test.*", "*Tests.*", "*_spec.*", "conftest.py"))
            or (kind([path]) != "docs"
                and any(part in {"scenarios", "fixtures", "validation", "checks"} for part in parts)
                and any(ASSERTION.match(line) for line in added_lines)))
