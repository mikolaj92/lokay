"""Read explicit issue file paths from one parent issue fact."""

from lokay.localize import extract_issue_file_paths


def read(issue_raw: dict) -> dict:
    return {
        "ok": True,
        "paths": list(extract_issue_file_paths(str(issue_raw.get("body") or ""))),
    }
