"""Purely reduce authored repository-slot reactions into one selection."""

from lokay.proc.catalog_work import remaining_ready_count, work_by_repo
from lokay.proc.pass_lane import (
    classify_pass_lane,
    classify_repo_lane,
    product_candidates,
    self_repo,
)


def reduce_state(*, prepared: dict, results: list[dict], working: dict) -> dict:
    actions = list(working.get("actions") or [])
    ready = work_by_repo(working, stuck=prepared.get("stuck"))
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
    if product_eligible:
        clean = [product_eligible[0]]
    elif oil_eligible:
        clean = [oil_eligible[0]]
    else:
        clean = []
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
