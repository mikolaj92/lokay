"""Classify one bounded stale-worktree candidate into keep or remove."""

from __future__ import annotations
from pathlib import Path
from lokay.git_worktree import leftover_status, remote_heads
from lokay.proc._common import runner
from lokay.proc.reap_stale_worktrees import _issue_is_closed


def classify(candidate: dict, *, live: bool) -> dict:
    if not candidate.get("present"):
        return {"ok": True, "route": "absent", "row": candidate}
    row = dict(candidate)
    protected = str(row.pop("protected", "") or "")
    if protected:
        return {
            "ok": True,
            "route": "keep",
            "row": {**row, "kept": True, "reason": protected},
        }
    if not live:
        return {
            "ok": True,
            "route": "keep",
            "row": {**row, "kept": True, "reason": "planned"},
        }
    issue = row.get("issue")
    if issue is not None and _issue_is_closed(str(row["repo"]), int(issue)) is True:
        return {"ok": True, "route": "remove", "row": {**row, "reason": "closed_issue"}}
    clone = Path(str(row["clone"]))
    path = Path(str(row["path"]))
    branch = str(row["branch"])
    if not clone.exists():
        return {
            "ok": True,
            "route": "keep",
            "row": {
                **row,
                "kept": True,
                "reason": "unreadability",
                "error": "clone_path missing",
            },
        }
    heads = remote_heads(runner(), clone)
    if heads is None:
        return {
            "ok": True,
            "route": "keep",
            "row": {
                **row,
                "kept": True,
                "reason": "unreadability",
                "error": "cannot list origin heads",
            },
        }
    status = leftover_status(
        runner(),
        path,
        clone,
        branch,
        base="main",
        fetch_base=False,
        known_published=branch in heads,
    )
    row.update(
        {
            k: status[k]
            for k in (
                "ahead",
                "behind_main",
                "published",
                "dirty",
                "uncommitted",
                "keep_unpublished",
            )
            if k in status
        }
    )
    if not status.get("readable"):
        reason = "unreadability"
        row["error"] = status.get("error")
    elif status.get("uncommitted") == "real":
        reason = "uncommitted_real"
    elif status.get("keep_unpublished"):
        reason = "unpublished_or_dirty"
    else:
        reason = "stale"
    row["reason"] = reason
    return {"ok": True, "route": "remove" if reason == "stale" else "keep", "row": row}
