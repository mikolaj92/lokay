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


def code_scope_issue(files: list[str], title: str, body: str | None, added: set[str] | None = None) -> dict | None:
    text = title + "\n" + (body or "")
    code = re.search(r"\.(?:py|ts|swift)\b|\bsrc/|\b(?:implement|fix|bug|dodać|naprawić|zaimplementować|błąd|refactor)\b", text, re.I)
    docs = re.search(r"\b(?:docs|dokumentacja|readme|opis)\b", text, re.I)
    # A docs word alone is not enough to override explicit production intent.
    docs_only = docs and (not code or re.search(r"\b(?:only|tylko)\b", text, re.I) or
                          not re.search(r"\.(?:py|ts|swift)\b|\bsrc/|\b(?:bug|błąd|refactor|implement|dodać|zaimplementować)\b", text, re.I))
    non_code = lambda path: is_test(path) or path.startswith("docs/") or PurePosixPath(path).suffix.lower() in (".md", ".rst", ".txt") or (added is not None and path in added and "scripts" in PurePosixPath(path).parts[:-1])
    if files and all(non_code(path) for path in files) and code and not docs_only:
        return {"warstwa": "scope", "plik": "", "log": "PR changes only docs/tests; the issue asks for a code change."}
    return None
