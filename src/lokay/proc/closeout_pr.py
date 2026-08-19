"""One job: checks → route → triage/repair/wait for one open AI PR."""

import argparse
from pathlib import Path
from typing import Any

from lokay.closeout import COUNTERS, apply_deltas, park_needs_review, pr_envelope, route_deltas, should_review_repair, triage_skip_deltas
from lokay.compose.pr_repair import compose_pr_repair
from lokay.compose.pr_triage import compose_pr_triage
from lokay.envelope import emit_exit
from lokay.passkit.support import is_manual_pr, run_proc
from lokay.proc import get_issue as p_get_issue, pr_checks as p_checks, unbounded_park as p_park
from lokay.proc._common import add_config_live
from lokay.proc.pr_route import run_pr_route
from lokay.stuck import clear_issue, issue_number_from_branch, save_stuck

MINI_MILL_REPO = "mikolaj92/lokay"
def run_closeout_pr(*, repo: str, pr: dict[str, Any], config_path: str | None, live: bool, merge_enabled: bool, require_checks: bool, repair_budget: int, executor_enabled: bool, branch_prefix: str, stuck: dict[str, Any], stuck_path: Path) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    c = {key: 0 for key in COUNTERS}
    progress = remaining_closed = 0
    n, head = int(pr["number"]), str(pr.get("head_ref") or "")
    cfg = ["--config", config_path] if config_path else []

    def done(route: str, reason: str = "", still_open: bool = True) -> dict[str, Any]:
        return pr_envelope(repo=repo, pr=n, route=route, reason=reason, still_open=still_open, actions=actions, repair_budget=repair_budget, progress=progress, remaining_closed=remaining_closed, counters=c)
    if repo != MINI_MILL_REPO:
        return done("skip", "repo_not_delivered_by_mini_mill")
    def repair(*, review: dict[str, Any] | None = None, step: str = "pr_repair") -> None:
        nonlocal repair_budget
        if not head or repair_budget <= 0 or not executor_enabled:
            return
        kw: dict[str, Any] = dict(config_path=config_path, repo=repo, pr_number=n, branch=head, live=True)
        if review is not None:
            kw["review"] = review
        actions.append({"step": step, "pr": n, "branch": head, **compose_pr_repair(**kw)})
        repair_budget -= 1
    issue_n = issue_number_from_branch(head, branch_prefix=branch_prefix)
    if issue_n is not None:
        fetched = run_proc(p_get_issue.main, [*cfg, "--repo", repo, "--issue", str(issue_n), "--live"])
        actions.append({"step": "get_issue", "repo": repo, "issue": issue_n, "pr": n, **fetched})
        state = str((fetched.get("issue") or {}).get("state") or "").upper()
        if fetched.get("ok") and state != "OPEN":
            if live:
                parked = run_proc(p_park.main, ["--repo", repo, "--issue", str(issue_n)])
                actions.append({"step": "park_closed_issue", "repo": repo, "issue": issue_n, "pr": n, **parked})
                clear_issue(stuck, repo, issue_n)
                save_stuck(stuck_path, stuck)
            return done("skip", "issue_closed")
    if is_manual_pr(pr):
        actions.append({"step": "skip_manual_pr", "repo": repo, "pr": n, "reason": "ai:needs-review is terminal/manual"})
        return done("skip", "manual")
    if str(pr.get("mergeable") or "").upper() in {"CONFLICTING", "DIRTY"}:
        return done("skip", "conflict")
    chk = run_proc(p_checks.main, [*cfg, "--repo", repo, "--pr", str(n)])
    actions.append({"step": "pr_checks", "pr": n, **chk})
    if not chk.get("ok"):
        return done("skip", "checks_error")
    routed = run_pr_route(checks=chk, merge_enabled=merge_enabled, require_checks=require_checks, labels=pr.get("labels"))
    route, reason = str(routed.get("route") or "skip"), str(routed.get("reason") or "")
    apply_deltas(c, route_deltas(route, reason))
    if route == "repair":
        if live:
            repair()
        return done("repair", reason)
    if route == "wait":
        return done("wait", reason)
    if route != "merge" or not live or not head:
        return done(route, reason)
    tri = compose_pr_triage(config_path=config_path, repo=repo, pr_number=n, branch=head, live=True)
    actions.append({"step": "pr_triage", "pr": n, "branch": head, **tri})
    if not tri.get("ok"):
        return done("merge", reason)
    if tri.get("skipped"):
        apply_deltas(c, triage_skip_deltas(tri))
        if should_review_repair(tri):
            repair(review=dict(tri.get("review") or {}), step="pr_review_repair")
        if park_needs_review(tri):
            pr["labels"] = ["ai:needs-review"]
        return done("merge", str(tri.get("reason") or ""))
    progress = remaining_closed = 1
    apply_deltas(c, {"mergeable_green": -1})
    if issue_n is not None:
        parked = run_proc(p_park.main, ["--repo", repo, "--issue", str(issue_n)])
        actions.append({"step": "park_closed_issue", "repo": repo, "issue": issue_n, "pr": n, **parked})
        clear_issue(stuck, repo, issue_n)
        save_stuck(stuck_path, stuck)
    return done("merge", reason, still_open=False)

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-closeout-pr")
    add_config_live(p)
    p.add_argument("--repo", required=True)
    p.add_argument("--pr", required=True, type=int)
    p.add_argument("--head-ref", default="")
    p.add_argument("--merge-enabled", action="store_true")
    a = p.parse_args(argv)
    return emit_exit(run_closeout_pr(repo=str(a.repo), pr={"number": a.pr, "head_ref": a.head_ref, "labels": []},
        config_path=a.config, live=bool(a.live), merge_enabled=bool(a.merge_enabled), require_checks=False,
        repair_budget=0, executor_enabled=False, branch_prefix="ai/fix/", stuck={"issues": {}}, stuck_path=Path("")))
