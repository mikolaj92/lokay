"""Park a sito close verdict. Label and comment; never close the issue."""

from __future__ import annotations

from lokay.tasks import TaskId
from lokay.github_tasks import catalog_row, issues_source


def apply(*, runner, cfg, repo: str, issue: int, issue_data: dict, decision: dict, live: bool) -> dict:
    reason = str(decision.get("reason") or "sito_mark")
    if not live:
        return {"ok": True, "planned": True, "verdict": "close", "marked": True, "reason": reason}
    row = catalog_row(cfg, repo)
    source = issues_source(row, runner=runner, config=cfg, live=True)
    identity = TaskId(source.plugin, source.target, int(issue))
    source.comment(identity, f"Parked (Lokay intake): {reason}.")
    task = source.mark(identity, "park")
    if str(task.state or "").upper() == "CLOSED":
        raise RuntimeError("sito must not close an open task")
    return {"ok": True, "applied": True, "verdict": "close", "marked": True, "reason": reason}
