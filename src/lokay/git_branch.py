from __future__ import annotations

import hashlib
import re

SAFE = re.compile(r"[^A-Za-z0-9._/-]+")


def branch_for_issue(prefix: str, repo: str, number: int, title: str = "") -> str:
    """Pure function: branch name only. No git I/O."""
    safe_prefix = SAFE.sub("-", prefix.strip("/"))
    slug = SAFE.sub("-", title.lower())[:40].strip("-") or "issue"
    digest = hashlib.sha256(f"{repo}#{number}".encode()).hexdigest()[:8]
    return f"{safe_prefix}/{number}-{slug}-{digest}"
