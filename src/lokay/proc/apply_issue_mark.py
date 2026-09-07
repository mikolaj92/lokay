"""Process a sito close verdict without limbo stamps.

Uses the tasks mark contract (no gh_issues import). Mark park strips ready /
stale limbo and does not stamp ai:frozen. Issue stays OPEN in queue.
"""

from __future__ import annotations

from lokay.tasks import TaskId
from lokay.github_tasks import catalog_row
from lokay.source import load_tasks


def apply(*, runner, cfg, repo: str, issue: int, issue_data: dict, decision: dict, live: bool) -> dict:
    reason = str(decision.get("reason") or "sito_mark")
    if not live:
        return {
            "ok": True,
            "planned": True,
            "verdict": "skip",
            "marked": False,
            "skipped": True,
            "reason": reason,
            "labels": [],
        }
    row = catalog_row(cfg, repo)
    source = load_tasks(row, runner=runner, config=cfg, live=True)
    identity = TaskId(source.plugin, source.target, int(issue))
    source.comment(
        identity,
        f"Skipped (Lokay intake): {reason}. No limbo label — issue stays open "
        "unless a last-resort close applies.",
    )
    task = source.mark(identity, "park")
    if str(task.state or "").upper() == "CLOSED":
        raise RuntimeError("sito must not close an open task")
    if "ai:frozen" in (task.labels or []):
        raise RuntimeError("sito must not stamp ai:frozen")
    return {
        "ok": True,
        "applied": True,
        "verdict": "skip",
        "marked": True,
        "skipped": True,
        "reason": reason,
        "labels": [],
    }
