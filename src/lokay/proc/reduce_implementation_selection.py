"""Purely reduce authored repository-slot reactions into one selection."""

from lokay.proc.catalog_work import remaining_ready_count, work_by_repo
from lokay.proc.pass_lane import (
    classify_pass_lane,
    classify_repo_lane,
    product_candidates,
    self_repo,
)

_PARKED_QUEUE = frozenset({"needs_human", "skip", "close"})


def parked_issue_keys(working: dict) -> set[tuple[str, int]]:
    """Issues already parked this pass (queue_conflict skip / human / close)."""
    keys: set[tuple[str, int]] = set()
    for action in list(working.get("actions") or []):
        if not isinstance(action, dict):
            continue
        if action.get("step") != "queue_conflict":
            continue
        if str(action.get("outcome") or "") not in _PARKED_QUEUE:
            continue
        repo = str(action.get("repo") or "")
        number = int(action.get("issue") or 0)
        if repo and number > 0:
            keys.add((repo, number))
    return keys


def drop_parked_rows(ready: dict, parked: set[tuple[str, int]]) -> dict:
    out: dict = {}
    for repo, rows in dict(ready or {}).items():
        kept = [
            row
            for row in list(rows or [])
            if (str(repo), int(row.get("number") or 0)) not in parked
        ]
        if kept:
            out[str(repo)] = kept
    return out


def eligible_with_work(repos: list[str], ready: dict) -> list[str]:
    """Keep every eligible catalog row that still has implementable work."""
    return [repo for repo in repos if list(ready.get(repo) or [])]


def reduce_state(*, prepared: dict, results: list[dict], working: dict) -> dict:
    actions = list(working.get("actions") or [])
    parked = parked_issue_keys(working)
    ready = drop_parked_rows(
        work_by_repo(working, stuck=prepared.get("stuck")), parked
    )
    remaining = remaining_ready_count(ready)
    self_id = str(prepared.get("self_repo") or self_repo())
    product_queue = bool(prepared.get("product_queue")) or product_candidates(
        ready_by_repo=ready,
        prs_by_repo=working.get("prs_by_repo"),
        self_id=self_id,
    )
    if prepared.get("route") == "no_budget":
        lane = classify_pass_lane(
            self_id=self_id,
            ready_by_repo=ready,
            prs_by_repo=working.get("prs_by_repo"),
        )
        return {
            "ok": True,
            "route": "no_budget",
            "clean_repos": [],
            "issue_budget": prepared.get("issue_budget"),
            "actions": actions,
            "ready_by_repo": ready,
            "remaining_ready": remaining,
            "lane": lane,
            "self_repo": self_id,
            "product_queue": product_queue,
        }
    product_eligible: list[str] = []
    oil_eligible: list[str] = []
    for row in results:
        repo, route, reason = (
            str(row.get("repo") or ""),
            str(row.get("route") or ""),
            str(row.get("reason") or ""),
        )
        if not repo:
            continue
        blocked = list(row.get("blocked") or [])
        if blocked:
            blocked_numbers = {int(item.get("number", -1)) for item in blocked}
            ready[repo] = [
                item
                for item in list(ready.get(repo) or [])
                if int(item.get("number", -1)) not in blocked_numbers
            ]
            remaining = remaining_ready_count(ready)
            actions.append(
                {
                    "step": "skip_stuck",
                    "repo": repo,
                    "exclude": sorted(blocked_numbers),
                    "reason": "issue is blocked in the stuck ledger; refuse issue_to_pr",
                }
            )
        if route == "eligible":
            if classify_repo_lane(repo, self_id=self_id) == "product":
                product_eligible.append(repo)
            else:
                oil_eligible.append(repo)
        if route == "ineligible":
            step = {
                "actionable_pr": "skip_ready_open_ai_pr",
                "occupied": "skip_ready_repo_occupied",
                "pr_survey_failed": "skip_issue_to_pr_survey_failed",
                "executor_disabled": "skip_ready_agent_disabled",
                "outside_scope": "skip_issue_to_pr_outside_mini_scope",
                "product_lane": "skip_oil_product_lane",
            }.get(reason, "skip_implementation_repo")
            actions.append({"step": step, "repo": repo, "reason": reason})
    product_left = eligible_with_work(product_eligible, ready)
    oil_left = eligible_with_work(oil_eligible, ready)
    if product_left:
        clean = product_left
    elif product_queue:
        clean = []
    elif oil_left:
        clean = oil_left
    else:
        clean = []
    remaining = remaining_ready_count(ready)
    lane = classify_pass_lane(
        self_id=self_id,
        ready_by_repo=ready,
        prs_by_repo=working.get("prs_by_repo"),
        clean_repos=clean,
    )
    return {
        "ok": True,
        "route": "selected" if clean else "none",
        "clean_repos": clean,
        "issue_budget": prepared.get("issue_budget"),
        "actions": actions,
        "ready_by_repo": ready,
        "remaining_ready": remaining,
        "lane": lane,
        "self_repo": self_id,
        "product_queue": product_queue,
    }
