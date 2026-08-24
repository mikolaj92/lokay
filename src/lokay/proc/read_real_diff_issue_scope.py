"""Read one optional explicit Files/Zmiana scope from an issue body."""

import re

from lokay.localize import extract_issue_file_paths

_HEADING = re.compile(r"(?im)^\s*#{1,6}\s+(?:zmiana|files?)\s*:?[ \t]*$")


def read(*, issue_body: str) -> dict:
    explicit = bool(_HEADING.search(issue_body))
    return {
        "ok": True,
        "route": "required" if explicit else "none",
        "paths": list(extract_issue_file_paths(issue_body)) if explicit else [],
    }
