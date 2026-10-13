from __future__ import annotations

import fnmatch
import re
from pathlib import PurePosixPath


def is_artifact(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return (path.endswith(".log") or path.startswith(".check-local/")
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
            line = re.sub(r"^\s*(?:[-*+] |\d+[.)] )", "", line).strip()
            paths = re.findall(r"`([^`]+)`", line) or line.split()[:1]
            planned.update(path.removeprefix("./").rstrip(":,") for path in paths)
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
