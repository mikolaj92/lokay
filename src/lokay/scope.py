from __future__ import annotations

import fnmatch
import re
from pathlib import Path, PurePosixPath


CACHE_PATTERNS = [
    ".cache/", ".build/", "DerivedData/", "node_modules/", "__pycache__/",
    ".pytest_cache/", ".ruff_cache/", ".mypy_cache/", ".venv/", ".check-local/",
    "*.pyc", "*.db-shm", "*.db-wal", "manifest.db",
]


def is_cache(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return any(fnmatch.fnmatchcase(part, pattern.rstrip("/"))
               for part in parts for pattern in CACHE_PATTERNS)


def is_artifact(path: str, worktree: Path | None = None) -> bool:
    parts = PurePosixPath(path).parts
    name = PurePosixPath(path).name
    return (is_cache(path) or path.endswith(("/", ".log", ".sqlite", ".sqlite-shm", ".sqlite-wal"))
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


def is_test(path: str) -> bool:
    parts = PurePosixPath(path).parts
    name = parts[-1] if parts else ""
    return "tests" in parts or any(fnmatch.fnmatchcase(name, pattern) for pattern in
                                   ("test_*.py", "*_test.py", "*.test.*", "*.spec.*"))


def matches_path(path: str, planned: str) -> bool:
    return (path == planned or (planned.endswith("/") and path.startswith(planned))
            or ("/" not in planned and PurePosixPath(path).name == planned))


def planned_files(plan_text: str, repo_files: list[str], diff_files: list[str]) -> set[str]:
    section = re.search(r"^## Pliki\s*\n(.*?)(?=^## |\Z)", plan_text, re.M | re.S)
    known = {path.removeprefix("./") for path in (*repo_files, *diff_files)}
    planned = set()
    read_only = False
    unchanged = re.compile(r"tylko do odczytu|tylko odczyt|bez zmian|nie zmieniać|read-only", re.IGNORECASE)
    if section:
        for line in section[1].splitlines():
            if (re.match(r"^\s*#{3,}\s", line)
                    or (line.rstrip("*_ ").endswith(":") and "`" not in line
                        and (unchanged.search(line) or not re.match(r"^\s*(?:[-*+]|\d+[.)])\s+", line)))):
                read_only = bool(unchanged.search(line))
                continue
            if read_only:
                continue
            item = re.match(r"^\s*(?:[-*+]|\d+[.)])\s+(.+)", line)
            if item:
                text = item[1].split("—", 1)[0].strip()
                description = re.split(r"[:—]", item[1], maxsplit=1)[1:]
            elif line.lstrip().startswith("|"):
                cells = line.lstrip().split("|")
                cell = cells[1].strip()
                description = cells[2:]
                if not cell or cell.lower() in ("plik", "file") or re.fullmatch(r":?-{3,}:?", cell):
                    continue
                text = cell
            else:
                continue
            if any(unchanged.match(part.strip(" \t*_")) for part in description):
                continue
            text = text.lstrip("*_[(")
            if not text:
                continue
            quoted = re.match(r"`([^`]+)`", text)
            path = (quoted[1] if quoted else text.split()[0].rstrip("*_:,;.)]")).removeprefix("./")
            if (not path or PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts
                    or (not quoted and not any(matches_path(known_path, path) for known_path in known))):
                continue
            planned.add(path)
    return planned


def code_scope_issue(files: list[str], plan: str, repo_files: list[str] | None = None) -> dict | None:
    planned = planned_files(plan, repo_files or [], files)
    if not planned:
        return None
    outside = [path for path in files if not any(matches_path(path, target) for target in planned)
               and not is_test(path)
               and not (PurePosixPath(path).name.endswith(".lock") or
                        PurePosixPath(path).name in ("package-lock.json", "npm-shrinkwrap.json"))]
    code = {path for path in planned if not is_test(path) and not path.startswith("docs/")
            and PurePosixPath(path).suffix.lower() not in (".md", ".rst", ".txt")}
    touches_code = any(matches_path(path, target) for path in files for target in code)
    reasons = []
    if code and not touches_code:
        reasons.append("Diff does not touch any planned code file: " + ", ".join(sorted(code)))
    if outside:
        reasons.append("Diff contains files outside ## Pliki: " + ", ".join(outside))
    if reasons:
        path = sorted(code)[0] if code and not touches_code else sorted(outside)[0]
        return {"warstwa": "scope", "plik": path, "linia_od": 1, "linia_do": 1, "log": "; ".join(reasons)}
    return None
