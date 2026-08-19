"""Queue contradiction gate: refuse / demote / defer before issue_to_pr.

Queue hygiene only — not a parallel scheduler. Prefer clear contradictions;
do not invent NEEDS_HUMAN distrust for intentional owner/assignee tickets.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping

from lokay.issue_checkboxes import is_bug_issue, work_checkbox_count
from lokay.models import Issue
from lokay.stuck import issue_number_from_branch, issue_numbers_covered_by_prs

READY = "ready"
SKIP = "skip"
CLOSE = "close"

_DEPENDS = re.compile(
    r"(?i)\b(?:depends\s+on|blocked\s+by|blocked\s+on|waiting\s+on|requires)\s+#(\d+)\b"
)
_PARENT_EPIC = re.compile(
    r"(?i)\b(?:parent\s+epic|child\s+of(?:\s+epic)?|part\s+of(?:\s+epic)?)\s*#(\d+)\b"
)
_SUPERSEDES = re.compile(
    r"(?i)\b(?:supersedes|superseded\s+by|duplicate\s+of|replaced\s+by)\s+#(\d+)\b"
)
_FIXES_ISSUE = re.compile(
    r"(?i)\b(?:fix(?:es)?|close[sd]?|resolve[sd]?)\s+#(\d+)\b"
)
_PATH = re.compile(
    r"(?:^|[\s`\"'(])("
    r"(?:src|tests|docs|scripts|fala|compose|apps?|packages?)/"
    r"[A-Za-z0-9_./\-]+\.[A-Za-z0-9]+"
    r")\b"
)
_EPIC_TITLE = re.compile(r"(?i)\b(?:epic|tracker)\b")


@dataclass
class ConflictVerdict:
    outcome: str  # ready | skip | close
    reason: str
    detail: dict[str, Any] = field(default_factory=dict)
    comment: str = ""
    add_labels: list[str] = field(default_factory=list)
    remove_labels: list[str] = field(default_factory=list)
    semantic: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _as_issue(raw: Issue | Mapping[str, Any]) -> Issue:
    if isinstance(raw, Issue):
        return raw
    return Issue.from_dict(dict(raw))


def _blob(issue: Issue) -> str:
    return f"{issue.title or ''}\n{issue.body or ''}"


def mentioned_paths(text: str) -> set[str]:
    return {m.group(1).strip().rstrip(".,);") for m in _PATH.finditer(text or "")}


def dependency_numbers(text: str) -> set[int]:
    return {int(m.group(1)) for m in _DEPENDS.finditer(text or "")}


def parent_epic_numbers(text: str) -> set[int]:
    return {int(m.group(1)) for m in _PARENT_EPIC.finditer(text or "")}


def supersession_numbers(text: str) -> set[int]:
    return {int(m.group(1)) for m in _SUPERSEDES.finditer(text or "")}


def fixes_issue_numbers(text: str) -> set[int]:
    return {int(m.group(1)) for m in _FIXES_ISSUE.finditer(text or "")}


def is_epic_like(issue: Issue) -> bool:
    labels = {str(x).lower() for x in (issue.labels or [])}
    if "ai:tracker" in labels:
        return True
    if _EPIC_TITLE.search(issue.title or ""):
        return True
    # Large *work* checkbox blobs are epic-shaped. A bug is one fix; template
    # Subsystem tags (## or **bold**) are routing, not children.
    if is_bug_issue(issue):
        return False
    return work_checkbox_count(issue.body or "") >= 6


def _peer_dict(raw: Mapping[str, Any] | Issue) -> dict[str, Any]:
    if isinstance(raw, Issue):
        return raw.to_dict()
    return dict(raw)


def _issue_refs_parent(child: Mapping[str, Any], parent_number: int) -> bool:
    blob = f"{child.get('title') or ''}\n{child.get('body') or ''}"
    if parent_number in parent_epic_numbers(blob):
        return True
    # Soft: "#N" alone in a "Parent epic" section heading line.
    return bool(
        re.search(
            rf"(?im)^#{{1,3}}\s*parent\s+epic[^\n]*#{parent_number}\b",
            blob,
        )
        or re.search(
            rf"(?im)^.*\bparent\s+epic\b.*#{parent_number}\b",
            blob,
        )
    )


def evaluate_queue_conflict(
    candidate: Issue | Mapping[str, Any],
    *,
    open_prs: Iterable[Mapping[str, Any]] = (),
    peer_issues: Iterable[Mapping[str, Any]] = (),
    branch_prefix: str = "ai/fix/",
    ready_label: str = "ai:ready",
    tracker_label: str = "ai:tracker",
) -> ConflictVerdict:
    """Deterministic contradiction check for one ready candidate.

    Outcomes:
    - ready: no clear contradiction
    - skip: defer to a later pass (leave labels; filter from this pass)
    - close: demote with receipt (drop ready; optional tracker label)
    Never returns needs_human.
    """
    issue = _as_issue(candidate)
    prs = [dict(p) for p in open_prs if isinstance(p, Mapping)]
    peers = [
        _peer_dict(p)
        for p in peer_issues
        if int((_peer_dict(p).get("number") or -1)) != int(issue.number)
    ]
    blob = _blob(issue)
    covered = issue_numbers_covered_by_prs(prs, branch_prefix=branch_prefix)

    # 1) Open AI PR already covers this issue number (branch or Fixes #N).
    covering = sorted(
        int(p["number"])
        for p in prs
        if p.get("number") is not None
        and (
            issue_number_from_branch(
                str(p.get("head_ref") or ""), branch_prefix=branch_prefix
            )
            == issue.number
            or issue.number
            in fixes_issue_numbers(f"{p.get('title') or ''}\n{p.get('body') or ''}")
        )
    )
    if issue.number in covered or covering:
        return ConflictVerdict(
            outcome=CLOSE,
            reason="open_ai_pr_covers_issue",
            detail={"issue": issue.number, "prs": covering or sorted(covered)},
            comment=(
                f"Lokay queue-conflict: open AI PR already covers #{issue.number}; "
                f"demoting `{ready_label}` (PR-first)."
            ),
            remove_labels=[ready_label],
        )

    # 2) Another open PR / peer explicitly supersedes this issue.
    for pr in prs:
        pr_blob = f"{pr.get('title') or ''}\n{pr.get('body') or ''}"
        if issue.number in supersession_numbers(pr_blob):
            return ConflictVerdict(
                outcome=CLOSE,
                reason="superseded_by_open_pr",
                detail={
                    "issue": issue.number,
                    "pr": int(pr["number"]),
                },
                comment=(
                    f"Lokay queue-conflict: open PR #{int(pr['number'])} supersedes "
                    f"#{issue.number}; demoting `{ready_label}`."
                ),
                remove_labels=[ready_label],
            )
    for peer in peers:
        peer_blob = f"{peer.get('title') or ''}\n{peer.get('body') or ''}"
        if issue.number in supersession_numbers(peer_blob):
            return ConflictVerdict(
                outcome=CLOSE,
                reason="superseded_by_open_issue",
                detail={
                    "issue": issue.number,
                    "by": int(peer["number"]),
                },
                comment=(
                    f"Lokay queue-conflict: open issue #{int(peer['number'])} supersedes "
                    f"#{issue.number}; demoting `{ready_label}`."
                ),
                remove_labels=[ready_label],
            )

    # 3) Epic / tracker with open children → demote epic; prefer children.
    if is_epic_like(issue):
        children = [
            int(p["number"])
            for p in peers
            if p.get("number") is not None and _issue_refs_parent(p, issue.number)
        ]
        if children:
            return ConflictVerdict(
                outcome=CLOSE,
                reason="epic_has_children_prefer_children",
                detail={"issue": issue.number, "children": sorted(children)},
                comment=(
                    f"Lokay queue-conflict: epic/tracker #{issue.number} has open "
                    f"children {sorted(children)}; demoting epic (prefer children)."
                ),
                remove_labels=[ready_label],
                add_labels=[tracker_label],
            )

    # 4) Unmet Depends on / Blocked by (dependency still open among peers).
    deps = dependency_numbers(blob)
    if deps:
        open_nums = {
            int(p["number"]) for p in peers if p.get("number") is not None
        }
        unmet = sorted(deps & open_nums)
        if unmet:
            return ConflictVerdict(
                outcome=SKIP,
                reason="dependency_unmet",
                detail={"issue": issue.number, "depends_on": unmet},
            )

    # 5) Same-path overlap with another ready/open peer or open AI PR → defer newer.
    cand_paths = mentioned_paths(blob)
    if cand_paths:
        for peer in peers:
            peer_paths = mentioned_paths(
                f"{peer.get('title') or ''}\n{peer.get('body') or ''}"
            )
            overlap = sorted(cand_paths & peer_paths)
            if not overlap:
                continue
            peer_n = int(peer["number"])
            # Defer the higher number so the older ticket keeps the lane.
            if issue.number > peer_n:
                return ConflictVerdict(
                    outcome=SKIP,
                    reason="path_overlap_with_peer",
                    detail={
                        "issue": issue.number,
                        "peer": peer_n,
                        "paths": overlap,
                    },
                )
        for pr in prs:
            pr_paths = mentioned_paths(
                f"{pr.get('title') or ''}\n{pr.get('body') or ''}"
            )
            overlap = sorted(cand_paths & pr_paths)
            if overlap:
                return ConflictVerdict(
                    outcome=SKIP,
                    reason="path_overlap_with_open_pr",
                    detail={
                        "issue": issue.number,
                        "pr": int(pr["number"]),
                        "paths": overlap,
                    },
                )

    return ConflictVerdict(
        outcome=READY,
        reason="no_clear_contradiction",
        detail={"issue": issue.number},
    )
