"""Pick one closed ticket kind. Never guess one.

A body line ``Kind: bug`` wins. Otherwise exactly one ``kind:<name>``
label. Two labels, an unknown name, or silence all mean no kind.
"""

from __future__ import annotations

import re

from lokay.models import Issue

KINDS = frozenset({"bug", "fix", "feat", "perf", "refactor", "chore"})
_LINE = re.compile(r"(?mi)^kind:\s*([a-z]+)\s*$")


def classify(issue: Issue) -> str:
    named = {match.group(1).lower() for match in _LINE.finditer(issue.body or "")}
    if len(named) == 1 and named <= KINDS:
        return next(iter(named))
    if named:
        return ""
    labels = {
        label.split(":", 1)[1].strip().lower()
        for label in (issue.labels or [])
        if label.lower().startswith("kind:")
    }
    if len(labels) == 1 and labels <= KINDS:
        return next(iter(labels))
    return ""
