"""Work checkboxes vs template metadata.

Issue templates (Subsystem / Environment / labels) use checkboxes as routing
tags. Those are not work slices. Counting them as an epic closes one bug and
mints junk children (Temida#4710 → Argus/Dike/…).
"""

from __future__ import annotations

import re

from lokay.models import Issue

_CHECKBOX = re.compile(r"(?m)^\s*[-*]\s*\[[ xX]\]\s*(.*)$")
_HEADING = re.compile(r"(?m)^(#{1,6})\s+(.+?)\s*$")
# GitHub issue templates often use bold labels, not ATX headings:
#   **Subsystem**\n- [ ] Argus
_BOLD_LABEL = re.compile(r"(?m)^\s*\*\*(.+?)\*\*\s*:?\s*$")
_BUG_TITLE = re.compile(r"(?i)\[\s*bugs?\s*\]")

# Routing / form sections: a checked name here is metadata, not a child issue.
_METADATA_HEADING = re.compile(
    r"(?i)^(?:"
    r"subsystem|subsystems|component|components|area|areas|"
    r"product|products|surface|surfaces|platform|host|repo|repos|"
    r"kind|severity|priority|model|assignee|labels?|type|category|"
    r"environment|env|"
    r"out\s*of\s*scope|out-of-scope|non-?goals?|not\s+in\s+(?:this\s+)?scope"
    r")\b"
)


def _section_title(raw: str) -> str | None:
    heading = _HEADING.match(raw)
    if heading:
        return heading.group(2).strip()
    bold = _BOLD_LABEL.match(raw)
    if bold:
        return bold.group(1).strip()
    return None


def iter_work_checkboxes(body: str) -> list[str]:
    """Checkbox item texts that are work, not template routing."""
    items: list[str] = []
    skip = False
    for raw in (body or "").splitlines():
        title = _section_title(raw)
        if title is not None:
            skip = bool(_METADATA_HEADING.search(title))
            continue
        if skip:
            continue
        match = _CHECKBOX.match(raw)
        if match:
            text = match.group(1).strip()
            if text:
                items.append(text)
    return items


def work_checkbox_count(body: str) -> int:
    return len(iter_work_checkboxes(body))


def is_bug_issue(issue: Issue) -> bool:
    """One symptom, one fix. Template routing tags are not an epic."""
    labels = {str(x).lower() for x in (issue.labels or [])}
    if labels & {"bug", "kind:bug", "type:bug"}:
        return True
    title = issue.title or ""
    if _BUG_TITLE.search(title):
        return True
    return bool(re.search(r"(?i)\bbug\b", title))
