"""Live host/fleet ops vs coding-slot work (#1041).

Pure detectors — never send Hermes restore / LaunchAgent / SSH host evidence
through one coding monolith. Zero needs_human.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from lokay.models import Issue

# Machine-readable park criterion stamped into park reason/summary.
HOST_OPS_UNPARK_CRITERION = (
    "auto-unpark when host evidence receipt exists / Hermes restored"
)

# Live fleet/host ops — tight; avoid ordinary code-only host_ff docs.
_HOST_OPS = re.compile(
    r"(?i)(?:"
    r"\bhermes\s+restore\b"
    r"|\brestore\s+(?:hermes|on\s+host(?:\s*\d+)?)\b"
    r"|\blaunchagent\b"
    r"|\bmini[-_]?m4(?:-\d+)?\b"
    r"|\bssh\s+host\b"
    r"|\bgrok\s+bot\s+computer\s+update\b"
    r"|\bfleet\s+host\s+evidence\b"
    r"|\bhost\s+evidence\b"
    r"|\bżywy\s+host\b"
    r"|\bzywy\s+host\b"
    r"|\blive\s+(?:fleet|host)\b"
    r"|\bhost\s*/\s*ops\b"
    r"|\bhost[-_]ops\b"
    r")"
)

# Product/code slice signals (monolith when combined with host_ops).
_CODE_PATH = re.compile(
    r"(?i)\b(?:src/|tests/|fala/)[A-Za-z0-9_.\-]+"
)
_CODE_WORK = re.compile(
    r"(?i)(?:"
    r"\bimplement\b"
    r"|\bpytest\b"
    r"|\bunit\s+tests?\b"
    r"|\b(?:add|write|land)\s+(?:a\s+)?(?:code|patch|pr)\b"
    r"|\bpull\s+request\b"
    r"|\bsrc/lokay\b"
    r"|\btool_contracts\b"
    r"|\bai/fix\b"
    r")"
)
_CODE_NEGATION = re.compile(
    r"(?i)\b(?:no|not|without|zero)\s+(?:a\s+)?(?:code|coding|pr|patch)\b"
    r"|\bnot\s+a\s+coding\s+slot\b"
    r"|\bhost\s+evidence\s+only\b"
)
_DONE_MEANS = re.compile(r"(?im)^#{1,3}\s*done\s*means\b")

# Line looks like host-ops-only work (filter from coding children).
_HOST_OPS_LINE = re.compile(
    r"(?i)(?:"
    r"hermes\s+restore|restore\s+(?:hermes|on\s+host)|launchagent|"
    r"mini[-_]?m4|ssh\s+host|grok\s+bot\s+computer|fleet\s+host|"
    r"host\s+evidence|żywy\s+host|zywy\s+host|live\s+(?:fleet|host)|"
    r"host\s*/\s*ops|host[-_]ops"
    r")"
)


def issue_requests_host_ops(issue: Issue) -> bool:
    """True when the issue asks for live host/fleet ops evidence."""
    blob = f"{issue.title or ''}\n{issue.body or ''}"
    return bool(_HOST_OPS.search(blob))


def _has_code_slice(issue: Issue) -> bool:
    blob = f"{issue.title or ''}\n{issue.body or ''}"
    if _CODE_PATH.search(blob):
        return True
    if _CODE_NEGATION.search(blob) and not _CODE_PATH.search(blob):
        # Explicit host-only / no-code wording without src/tests/fala paths.
        if not _CODE_WORK.search(blob):
            return False
    if _CODE_WORK.search(blob):
        return True
    return False


def issue_is_host_ops_monolith(issue: Issue) -> bool:
    """Host ops AND product/code work in one ticket — must split, not code."""
    if not issue_requests_host_ops(issue):
        return False
    return _has_code_slice(issue)


def line_is_host_ops_only(text: str) -> bool:
    """True when a checkbox/heading line is host-ops work, not a coding child."""
    return bool(_HOST_OPS_LINE.search(text or ""))


def host_ops_child_body(parent: Issue, *, criterion: str = HOST_OPS_UNPARK_CRITERION) -> str:
    """Deterministic host/ops child — NOT a coding slot."""
    parent_ref = f"{parent.repo}#{parent.number}"
    return (
        "## Goal\n"
        "Deterministic host/fleet ops evidence for the parent. "
        "This is NOT a coding slot — do not route to issue_to_pr / ai/fix.\n\n"
        "## Done means\n"
        f"- [ ] {criterion}\n"
        "- [ ] Keep parent skipped (no limbo label) until evidence exists "
        "(factory skip; zero needs_human)\n\n"
        f"## Parent\nSplit from {parent_ref}: {parent.title}\n"
        f"\n<!-- lokay-host-ops:{criterion} -->\n"
    )


def host_ops_unpark_ready(
    issue: Issue,
    *,
    evidence: Mapping[str, Any] | None = None,
) -> bool:
    """Pure gate: frozen host_ops may wake when evidence receipt is present.

    ``evidence`` may carry keys such as ``host_evidence_receipt``,
    ``hermes_restored``, or a truthy ``ready`` flag. Does not mutate GitHub.
    """
    blob = f"{issue.title or ''}\n{issue.body or ''}"
    if not issue_requests_host_ops(issue) and "lokay-host-ops:" not in blob:
        return False
    ev = dict(evidence or {})
    if ev.get("ready") is True:
        return True
    if ev.get("host_evidence_receipt") or ev.get("hermes_restored"):
        return True
    # Comment/body stamped criterion satisfied by explicit receipt path.
    receipt = str(ev.get("receipt_path") or ev.get("receipt") or "").strip()
    return bool(receipt)
