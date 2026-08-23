"""Purely reduce explicit PR-closeout slot results into pass state."""

from lokay.closeout import COUNTERS
from lokay.passkit.support import is_manual_pr


def _apply(row, prs, merged, failures):
    repo = str(row.get("repo") or "")
    if not repo:
        return 0
    if row.get("route") in {"failed", "needs_human"}:
        failures.append({"repo": repo, "reason": row.get("reason") or row.get("error")})
    if row.get("still_open") is False:
        prs[repo] = []
        merged.append(repo) if repo not in merged else None
    if row.get("park_manual") and prs.get(repo):
        prs[repo][0]["labels"] = ["ai:needs-review"]
    return int(row.get("progress") or 0) if row.get("still_open") is False else 0


def reduce_state(*, prepared: dict, rows: list[dict], working: dict) -> dict:
    state = dict(working)
    prs = {k: list(v) for k, v in dict(state.get("prs_by_repo") or {}).items()}
    merged = [str(x) for x in state.get("merged_this_pass") or [] if x]
    failures = []
    totals = {
        k: int(state.get(k) or 0) + sum(int(r.get(k) or 0) for r in rows)
        for k in COUNTERS
    }
    progress = int(state.get("progress") or 0) + sum(
        _apply(row, prs, merged, failures) for row in rows
    )
    actions = list(state.get("actions") or [])
    for row in rows:
        actions.extend(row.get("actions") or [])
    present = [row for row in rows if row.get("repo")]
    budget = (
        int(present[-1].get("repair_budget", prepared.get("repair_budget") or 0))
        if present
        else int(prepared.get("repair_budget") or 0)
    )
    state.update(
        actions=actions,
        progress=progress,
        prs_by_repo=prs,
        merged_this_pass=merged,
        remaining_prs=sum(len(v) for v in prs.values()),
        actionable_prs=sum(not is_manual_pr(x) for v in prs.values() for x in v),
        manual_prs=sum(is_manual_pr(x) for v in prs.values() for x in v),
        **totals,
    )
    return {
        "ok": not failures,
        "state": state,
        "repair_budget": budget,
        "failures": failures,
    }
