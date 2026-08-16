"""Work checkboxes vs template metadata.

Issue templates (Subsystem / Environment / labels) use checkboxes as routing
tags. Those are not work slices. Counting them as an epic closes one bug and
mints junk children (Temida#4710 → Argus/Dike/…).
"""

from __future__ import annotations

import re

_CHECKBOX = re.compile(r"(?m)^\s*[-*]\s*\[[ xX]\]\s*(.*)$")
_HEADING = re.compile(r"(?m)^(#{1,6})\s+(.+?)\s*$")

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


def iter_work_checkboxes(body: str) -> list[str]:
    """Checkbox item texts that are work, not template routing."""
    items: list[str] = []
    skip = False
    for raw in (body or "").splitlines():
        heading = _HEADING.match(raw)
        if heading:
            skip = bool(_METADATA_HEADING.search(heading.group(2).strip()))
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
