"""Record a factory skip for a former park path — no limbo label stamp."""

from __future__ import annotations

from lokay.gh_issues import comment_issue


def apply(
    *,
    runner,
    cfg,
    repo: str,
    issue: int,
    decision: dict,
    live: bool,
    park_stop: dict | None = None,
) -> dict:
    stop = dict(park_stop or {})
    if park_stop is not None and stop.get("route") not in {"park", "skip"}:
        return {
            "ok": False,
            "route": "fail",
            "error": "park_stop_not_admitted",
            "verdict": "skip",
        }
    reason = str(stop.get("reason") or decision.get("reason") or "skip")
    summary = str(stop.get("summary") or decision.get("summary") or "").strip()
    if not live:
        return {
            "ok": True,
            "planned": True,
            "verdict": "skip",
            "route": "skip",
            "labels": [],
            "reason": reason,
        }
    # Never stamp ai:frozen / needs-feedback / blocked. Optional receipt comment only.
    note = f"Skipped by factory (Lokay): {reason}. No limbo label — issue stays open in queue."
    if summary:
        note = f"{note} {summary}."
    comment_issue(runner, repo, issue, note, live=True)
    return {
        "ok": True,
        "applied": True,
        "verdict": "skip",
        "route": "skip",
        "labels": [],
        "reason": reason,
        "skipped": True,
    }
