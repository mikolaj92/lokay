"""Scan added diff lines before a blueprint commit is published."""
import re

_SECRET = re.compile(r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*\S+")
_CONFLICT = re.compile(r"^(<<<<<<<|=======|>>>>>>>)")


def scan_added(diff):
    secrets = False
    conflict = False
    for line in diff.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue
        added = line[1:]
        secrets = secrets or _SECRET.search(added) is not None
        conflict = conflict or _CONFLICT.search(added) is not None
    return {"secrets_hit": secrets, "conflict_markers": conflict}
