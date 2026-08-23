"""Persist one explicit triage dispatch outcome to the pass ledger."""

from lokay.passkit import io as pass_io


def record(*, pass_dir: str, outcome: dict) -> dict:
    route = str(outcome.get("route") or "none")
    if route == "none":
        return {"ok": True, "applied": False, "route": "done", "ran": 0}
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    route = str(outcome.get("route") or "failed")
    repo = str(outcome.get("repo") or "")
    issue = int(outcome.get("issue") or 0)
    triage = dict(outcome.get("triage") or {})
    action = {
        "step": "issue_triage" if route != "blocked" else "skip_stuck",
        "repo": repo,
        "issue": issue,
    }
    if route == "blocked":
        action.update(
            ok=True, skipped=True, blocked=True, reason="blocked_in_stuck_ledger"
        )
    elif route == "failed":
        action.update(
            ok=False,
            engine="fala",
            error=str(outcome.get("error") or "Fala path failed"),
        )
    else:
        action.update(triage)
    progress = int(working.get("progress") or 0)
    remaining = int(working.get("remaining_inbox") or 0)
    by_repo = dict(working.get("inbox_by_repo") or {})
    decision = triage.get("decision")
    skipped = (
        triage.get("skipped")
        or isinstance(decision, dict)
        and decision.get("decision") == "skip"
    )
    if (
        route == "completed"
        and triage.get("ok")
        and triage.get("applied") is True
        and not skipped
    ):
        progress += 1
        remaining = max(0, remaining - 1)
        by_repo[repo] = max(0, int(by_repo.get(repo) or 0) - 1)
    working.update(
        actions=[*list(working.get("actions") or []), action],
        progress=progress,
        remaining_inbox=remaining,
        inbox_by_repo=by_repo,
    )
    pass_io.write_json(pass_io.working_path(pass_dir), working)
    return {
        "ok": True,
        "applied": True,
        "route": "done",
        "ran": 1 if route in {"completed", "failed"} else 0,
    }
