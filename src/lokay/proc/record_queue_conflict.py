"""Persist one closed queue-conflict outcome in the pass workspace."""

from lokay.passkit.io import read_json, working_path, write_json


def record(*, pass_dir: str, outcome: dict, remove: dict, tracker: dict) -> dict:
    if outcome.get("route") == "none":
        return {"ok": True, "route": "none"}
    working = read_json(working_path(pass_dir))
    repo, number = str(outcome.get("repo") or ""), int(outcome.get("issue") or 0)
    decision = dict(outcome.get("decision") or {})
    route = str(outcome.get("route") or "needs_human")
    ready = dict(working.get("ready_by_repo") or {})
    inbox = dict(working.get("inbox_issues_by_repo") or {})
    if route != "ready":
        ready[repo] = [
            row
            for row in list(ready.get(repo) or [])
            if int(row.get("number") or 0) != number
        ]
        inbox[repo] = [
            row
            for row in list(inbox.get(repo) or [])
            if int(row.get("number") or 0) != number
        ]
        working["remaining_ready"] = max(
            0, int(working.get("remaining_ready") or 0) - 1
        )
        working["inbox_issues_by_repo"] = inbox
    action = {
        "step": "queue_conflict",
        "repo": repo,
        "issue": number,
        "outcome": route,
        "reason": decision.get("reason"),
        "detail": decision.get("detail") or {},
        "semantic": True,
    }
    if route == "close":
        action["remove_ready"] = remove
        action["add_tracker"] = tracker
        working["progress"] = int(working.get("progress") or 0) + int(
            bool(remove.get("applied") or tracker.get("applied"))
        )
    working["ready_by_repo"] = ready
    working["actions"] = [*list(working.get("actions") or []), action]
    write_json(working_path(pass_dir), working)
    return {
        "ok": True,
        "route": route,
        "decision": decision,
        "repo": repo,
        "issue": number,
    }
