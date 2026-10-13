from __future__ import annotations

import fnmatch
import re
from pathlib import PurePosixPath


CACHE_PATTERNS = [
    ".cache/", ".build/", "DerivedData/", "node_modules/", "__pycache__/",
    ".pytest_cache/", ".ruff_cache/", ".mypy_cache/", ".venv/", ".check-local/",
    "*.pyc", "*.db-shm", "*.db-wal", "manifest.db",
]


def is_cache(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return any(fnmatch.fnmatchcase(part, pattern.rstrip("/"))
               for part in parts for pattern in CACHE_PATTERNS)


def is_artifact(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return (is_cache(path) or path.endswith(".log") or path.startswith(".validation/")
            or (path.startswith("tmp/") and path.endswith(".lock"))
            or parts[-2:] == ("bin", "gh"))


def is_test(path: str) -> bool:
    parts = PurePosixPath(path).parts
    name = parts[-1] if parts else ""
    return "tests" in parts or any(fnmatch.fnmatchcase(name, pattern) for pattern in
                                   ("test_*.py", "*_test.py", "*.test.*", "*.spec.*"))


def code_scope_issue(files: list[str], plan: str) -> dict | None:
    section = re.search(r"^## Pliki\s*\n(.*?)(?=^## |\Z)", plan, re.M | re.S)
    planned = set()
    if section:
        for line in section[1].splitlines():
            item = re.match(r"^\s*(?:[-*+]|\d+[.)])\s+(.+)", line)
            if not item:
                continue
            text = item[1].split("—", 1)[0].strip().removeprefix("**")
            if not text:
                continue
            quoted = re.match(r"`([^`]+)`", text)
            path = quoted[1] if quoted else text.split()[0]
            planned.add(path.rstrip(":,").removesuffix("**").rstrip(":,").removeprefix("./"))
    outside = [path for path in files if path not in planned and not is_test(path)
               and not (PurePosixPath(path).name.endswith(".lock") or
                        PurePosixPath(path).name in ("package-lock.json", "npm-shrinkwrap.json"))]
    code = {path for path in planned if not is_test(path) and not path.startswith("docs/")
            and PurePosixPath(path).suffix.lower() not in (".md", ".rst", ".txt")}
    reasons = []
    if code and not code.intersection(files):
        reasons.append("Diff does not touch any planned code file: " + ", ".join(sorted(code)))
    if outside:
        reasons.append("Diff contains files outside ## Pliki: " + ", ".join(outside))
    if reasons:
        return {"warstwa": "scope", "plik": "", "log": "; ".join(reasons)}
    return None
