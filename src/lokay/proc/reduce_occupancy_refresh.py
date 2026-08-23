"""Purely reduce receipt facts and repository PR-refresh reactions."""

from lokay.passkit.support import is_manual_pr
from lokay.passkit.working import recount_prs


def _keep_parked(previous: list[dict], rows: list[dict]) -> list[dict]:
    prev = {int(x["number"]): x for x in previous if x.get("number") is not None}
    out = []
    for row in rows:
        parked = prev.get(int(row["number"])) if row.get("number") is not None else None
        if parked is not None and is_manual_pr(parked) and not is_manual_pr(row):
            row = {**row, "labels": [*list(row.get("labels") or []), "ai:needs-review"]}
        out.append(row)
    return out


def reduce_state(*, facts: dict, results: list[dict], working: dict) -> dict:
    actions = list(working.get("actions") or [])
    previous = dict(working.get("prs_by_repo") or {})
    prs = {}
    failed = set(working.get("pr_survey_failed") or [])
    for receipt in facts.get("cleared") or []:
        actions.append(
            {
                "step": "clear_issue_to_pr_receipt",
                "repo": receipt.get("repo"),
                "issue": receipt.get("issue"),
            }
        )
    for row in results:
        repo = str(row.get("repo") or "")
        route = str(row.get("route") or "")
        if not repo:
            continue
        if route in {"occupied", "no_ready"}:
            actions.append(
                {"step": "refresh_prs_skipped", "repo": repo, "reason": route}
            )
            prs[repo] = list(row.get("previous") or [])
        elif route == "failed":
            actions.append(
                {"step": "refresh_prs", "repo": repo, **dict(row.get("listed") or {})}
            )
            failed.add(repo)
            prs[repo] = list(row.get("previous") or [])
        else:
            actions.append(
                {"step": "refresh_prs", "repo": repo, **dict(row.get("listed") or {})}
            )
            failed.discard(repo)
            prs[repo] = _keep_parked(
                list(row.get("previous") or []),
                list((row.get("listed") or {}).get("prs") or []),
            )
    state = {
        **working,
        "actions": actions,
        "prs_by_repo": prs,
        "pr_survey_failed": sorted(failed),
        "survey_errors": len(working.get("inbox_survey_failed") or [])
        + len(working.get("ready_survey_failed") or [])
        + len(failed),
        "merged_this_pass": list(facts.get("merged") or []),
        "live_issue_to_pr_repos": list(facts.get("live_repos") or []),
        "occupied_repos": list(facts.get("occupied") or []),
        "issue_to_pr_started": int(facts.get("live_receipt_count") or 0),
        "cleared_issue_to_pr_receipts": [
            {"repo": x.get("repo"), "issue": x.get("issue")}
            for x in facts.get("cleared") or []
        ],
        "receipt_state_unknown": bool(facts.get("receipt_state_unknown")),
    }
    recount_prs(state)
    return {"ok": True, "state": state}
