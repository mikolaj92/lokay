"""Deterministic auto-split of oversized issues into bounded child issues.

Pure rules — no coding harness. Fail closed when parts cannot be extracted:
callers apply NEEDS_HUMAN instead of inventing work.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from lokay.issue_checkboxes import is_bug_issue, iter_work_checkboxes
from lokay.models import Issue

MAX_CHILDREN = 5
MIN_CHILDREN = 2
_MAX_TITLE = 72

_NUMBERED = re.compile(r"(?m)^\s*\d+[.)]\s+(.+)$")
_H2 = re.compile(r"(?m)^#{2,3}\s+(.+)$")
_SKIP_HEADINGS = re.compile(
    r"(?i)^(goal|goals|done\s*means|non-?goals?|out\s*of\s*scope|"
    r"parent\s+epic|context|background|notes?|references?)\b"
)


@dataclass(frozen=True)
class ChildSpec:
    """One planned child issue (not yet created)."""

    title: str
    body: str
    source: str  # checkbox | numbered | heading | inventory_slice

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SplitPlan:
    """Bounded child plan for one parent issue."""

    reason: str
    children: tuple[ChildSpec, ...] = ()
    demote_parent: bool = True
    close_parent: bool = True
    parent_tracker_label: str = "ai:tracker"
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["children"] = [c.to_dict() for c in self.children]
        return data


def _clip_title(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    cleaned = cleaned.rstrip(".")
    if len(cleaned) <= _MAX_TITLE:
        return cleaned
    return cleaned[: _MAX_TITLE - 1].rstrip() + "…"


def _child_body(parent: Issue, part_title: str, part_detail: str) -> str:
    parent_ref = f"{parent.repo}#{parent.number}"
    return (
        f"## Goal\n{part_detail.strip() or part_title.strip()}\n\n"
        f"## Done means\n- [ ] {part_title.strip()}\n\n"
        f"## Parent\nSplit from {parent_ref}: {parent.title}\n"
    )


def _from_checkboxes(parent: Issue) -> list[ChildSpec]:
    items = [m.strip() for m in iter_work_checkboxes(parent.body or "") if m.strip()]
    out: list[ChildSpec] = []
    for item in items[:MAX_CHILDREN]:
        title = _clip_title(item)
        out.append(
            ChildSpec(
                title=title,
                body=_child_body(parent, title, item),
                source="checkbox",
            )
        )
    return out


def _from_numbered(parent: Issue) -> list[ChildSpec]:
    items = [m.strip() for m in _NUMBERED.findall(parent.body or "") if m.strip()]
    out: list[ChildSpec] = []
    for item in items[:MAX_CHILDREN]:
        title = _clip_title(item)
        out.append(
            ChildSpec(
                title=title,
                body=_child_body(parent, title, item),
                source="numbered",
            )
        )
    return out


def _from_headings(parent: Issue) -> list[ChildSpec]:
    headings = [m.strip() for m in _H2.findall(parent.body or "") if m.strip()]
    usable = [h for h in headings if not _SKIP_HEADINGS.search(h)]
    out: list[ChildSpec] = []
    for heading in usable[:MAX_CHILDREN]:
        title = _clip_title(heading)
        out.append(
            ChildSpec(
                title=title,
                body=_child_body(parent, title, f"Implement: {heading}"),
                source="heading",
            )
        )
    return out


def _inventory_slices(parent: Issue) -> list[ChildSpec]:
    """Last-resort slices for inventory/epic blobs with no extractable parts."""
    title = (parent.title or "work").strip()
    seeds = (
        f"Scope inventory for: {title}",
        f"First implementable slice from: {title}",
    )
    return [
        ChildSpec(
            title=_clip_title(seed),
            body=_child_body(parent, seed, seed),
            source="inventory_slice",
        )
        for seed in seeds
    ]


def plan_split(
    issue: Issue,
    *,
    reason: str = "too_large_split",
    max_children: int = MAX_CHILDREN,
) -> SplitPlan | None:
    """Return a bounded child plan, or None when split is not deterministic."""
    # One symptom, one repair. Never mint Argus/Dike children from a bug form.
    if is_bug_issue(issue) and reason in {"too_many_checkboxes", "too_large_split"}:
        return None

    cap = max(MIN_CHILDREN, min(int(max_children), MAX_CHILDREN))
    candidates = _from_checkboxes(issue)
    if len(candidates) < MIN_CHILDREN:
        candidates = _from_numbered(issue)
    if len(candidates) < MIN_CHILDREN:
        candidates = _from_headings(issue)
    if len(candidates) < MIN_CHILDREN and reason in {
        "inventory_everything",
        "multi_epic_blob",
        "triage_split_candidate",
        "too_large_split",
    }:
        # Inventory/epic without parts: still file two scoped children so work moves.
        candidates = _inventory_slices(issue)

    if len(candidates) < MIN_CHILDREN:
        return None

    children = tuple(candidates[:cap])
    return SplitPlan(
        reason=reason,
        children=children,
        demote_parent=True,
        close_parent=True,
        detail={"extracted": len(children), "cap": cap, "parent": f"{issue.repo}#{issue.number}"},
    )


def stable_child_marker(parent: Issue, slot: int) -> str:
    """Idempotent marker independent of retries and generated issue numbers."""
    return f"<!-- lokay-split:{parent.repo}#{parent.number}:child:{int(slot)} -->"


def validate_split_plan(plan: dict[str, Any], *, parent: Issue) -> dict[str, Any]:
    children = list(plan.get("children") or [])
    if not MIN_CHILDREN <= len(children) <= MAX_CHILDREN:
        return {"valid": False, "reason": "child_count_out_of_bounds"}
    graph: dict[int, list[int]] = {}
    for slot, child in enumerate(children, 1):
        if not str(child.get("title") or "").strip() or "## Done means" not in str(child.get("body") or ""):
            return {"valid": False, "reason": "child_not_implementable", "slot": slot}
        deps = [int(value) for value in child.get("depends_on") or []]
        if any(value < 1 or value > len(children) or value == slot for value in deps):
            return {"valid": False, "reason": "invalid_dependency", "slot": slot}
        graph[slot] = deps
    visiting: set[int] = set(); visited: set[int] = set()
    def visit(node: int) -> bool:
        if node in visiting: return False
        if node in visited: return True
        visiting.add(node)
        if any(not visit(dep) for dep in graph[node]): return False
        visiting.remove(node); visited.add(node); return True
    if any(not visit(node) for node in graph):
        return {"valid": False, "reason": "dependency_cycle"}
    return {"valid": True, "reason": "validated", "child_count": len(children), "parent": f"{parent.repo}#{parent.number}"}


def parent_tracker_comment(plan: SplitPlan, child_numbers: list[int]) -> str:
    refs = ", ".join(f"#{n}" for n in child_numbers) or "(planned)"
    return (
        f"Split (lokay): parent closed as tracker. Children: {refs}. "
        f"Reason: {plan.reason}."
    )
