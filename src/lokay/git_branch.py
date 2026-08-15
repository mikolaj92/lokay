from __future__ import annotations

import hashlib
import re

# Prefix may keep a single path separator (`ai/fix`). Title slug must not:
# a leftover `/` makes a nested ref GitHub cannot use as a PR head.
SAFE_PREFIX = re.compile(r"[^A-Za-z0-9._/-]+")
SAFE_SLUG = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize_slug(title: str) -> str:
    """Collapse a ticket title into a git-safe slug (no ``..`` segment)."""
    slug = SAFE_SLUG.sub("-", title.lower())[:40]
    while ".." in slug:
        slug = slug.replace("..", "-")
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip(".-") or "issue"
    # A ref segment must not end with a dot (git check-ref-format).
    slug = re.sub(r"\.(?=-|$)", "", slug)
    slug = re.sub(r"-+", "-", slug).strip(".-") or "issue"
    return slug


def branch_for_issue(prefix: str, repo: str, number: int, title: str = "") -> str:
    """Pure function: branch name only. No git I/O."""
    safe_prefix = SAFE_PREFIX.sub("-", prefix.strip("/")).strip("-")
    slug = _sanitize_slug(title)
    digest = hashlib.sha256(f"{repo}#{number}".encode()).hexdigest()[:8]
    head = f"{number}-{slug}-{digest}"
    if not safe_prefix or "/" in head:
        raise ValueError(f"branch is not a single GitHub PR head: {safe_prefix}/{head}")
    return f"{safe_prefix}/{head}"
