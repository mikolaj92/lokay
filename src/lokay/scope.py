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
    ".pytest_cache/", ".ruff_cache/", ".mypy_cache/", ".venv/", ".check-local/",
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


def matches_path(path: str, planned: str) -> bool:
    return (path == planned or (planned.endswith("/") and path.startswith(planned))
            or ("/" not in planned and PurePosixPath(path).name == planned))


def planned_files(plan_text: str, repo_files: list[str], diff_files: list[str]) -> set[str]:
    return _planned_files(plan_text, repo_files, diff_files)


def legacy_planned_files(plan_text: str, repo_files: list[str], diff_files: list[str]) -> set[str]:
    return _planned_files(plan_text, repo_files, diff_files, real_paths=False)


def required_files(plan_text: str, repo_files: list[str], diff_files: list[str]) -> set[str]:
    lists = plan_file_lists(plan_text)
    return lists["Wymagane"] if lists is not None else set()


NEW_FILE_MARKER = " (nowy plik)"


def required_path_errors(rows: Sequence[tuple[str, bool]], existing: set[str] | None = None) -> list[str]:
    bad = []
    for path, new in rows:
        try:
            target = Path(path)
            valid = (bool(re.fullmatch(r"[^`\s:]+", path))
                     and not target.is_absolute() and ".." not in target.parts
                     and bool("/" in path or target.suffix))
            if existing is not None:
                valid = valid and ((path not in existing) if new else (path in existing))
        except (OSError, ValueError, RuntimeError):
            valid = False
        if not valid:
            bad.append(path)
    return sorted(set(bad))


def plan_file_lists(plan_text: str) -> dict[str, set[str]] | None:
    rows = _plan_file_rows(plan_text)
    return {name: {path for path, new in items} for name, items in rows.items()} if rows is not None else None


def plan_required_path_errors(plan_text: str, existing: set[str] | None = None) -> list[str]:
    rows = _plan_file_rows(plan_text)
    return required_path_errors(sorted(rows["Wymagane"]), existing) if rows is not None else []


def _plan_file_rows(plan_text: str) -> dict[str, set[tuple[str, bool]]] | None:
    section = re.search(r"^## Pliki\s*\n(.*?)(?=^## |\Z)", plan_text, re.M | re.S)
    if not section:
        return None
    lists: dict[str, set[tuple[str, bool]]] = {}
    current = None
    for line in section[1].splitlines():
        if not line.strip():
            continue
        if line in ("### Wymagane", "### Warunkowe"):
            current = line[4:]
            if current in lists:
                return None
            lists[current] = set()
            continue
        item = re.fullmatch(r"- `?([^`\s:]+)`?(" + re.escape(NEW_FILE_MARKER) + r")?:\s*(.+)", line)
        if current is None or item is None:
            return None
        path = item[1].removeprefix("./")
        if (not ("/" in path or PurePosixPath(path).suffix)
                or PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts):
            return None
        if current == "Warunkowe":
            condition = item[3].partition("warunek:")[2].split("[źródła:", 1)[0].strip()
            if not condition:
                return None
        lists[current].add((path, bool(item[2])))
    return lists if lists.get("Wymagane") is not None else None


def _planned_files(plan_text: str, repo_files: list[str], diff_files: list[str], *, real_paths: bool = True) -> set[str]:
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
            if (not path or (real_paths and not ("/" in path or PurePosixPath(path).suffix))
                    or PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts
                    or (not quoted and not any(matches_path(known_path, path) for known_path in known))):
                continue
            planned.add(path)
    return planned


def planned_code_touch_reason(files: Sequence[str] | set[str], code: set[str]) -> str | None:
    if code and not any(matches_path(path, target) for path in files for target in code):
        return "Diff does not touch any planned code file: " + ", ".join(sorted(code))
    return None


def code_scope_issue(files: list[str], plan: str, repo_files: list[str] | None = None,
                     plan_schema: int | None = None) -> dict | None:
    planned = planned_files(plan, repo_files or [], files)
    if not planned:
        return None
    outside = [path for path in files if not any(matches_path(path, target) for target in planned)
               and not is_test(path)
               and not (PurePosixPath(path).name.endswith(".lock") or
                        PurePosixPath(path).name in ("package-lock.json", "npm-shrinkwrap.json"))]
    code = {path for path in planned if not is_test(path) and not path.startswith("docs/")
            and PurePosixPath(path).suffix.lower() not in (".md", ".rst", ".txt")}
    touch_reason = planned_code_touch_reason(files, code) if plan_schema != 2 else None
    reasons = [touch_reason] if touch_reason else []
    if outside:
        reasons.append("Diff contains files outside ## Pliki: " + ", ".join(outside))
    if reasons:
        path = sorted(code)[0] if touch_reason else sorted(outside)[0]
        return {"warstwa": "scope", "plik": path, "linia_od": 1, "linia_do": 1, "log": "; ".join(reasons)}
    return None
