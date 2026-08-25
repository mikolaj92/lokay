"""Classify one repository against physical implementation gates."""

from lokay.passkit import io as pass_io
from lokay.passkit.support import is_manual_pr
from lokay.proc.catalog_work import implementable_rows, work_by_repo
from lokay.proc.pass_lane import is_oil_repo, product_candidates, self_repo
from lokay.stuck import excluded_numbers, issue_numbers_covered_by_prs


def inspect(*, pass_dir: str, prepared: dict, selected: dict) -> dict:
    repo = str(selected["repo"])
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    begin = pass_io.read_json(pass_io.begin_path(pass_dir))
    prefix = str(begin.get("branch_prefix") or "ai/fix/")
    work = work_by_repo(
        working,
        stuck=prepared.get("stuck"),
        branch_prefix=prefix,
    )
    raw = list((working.get("ready_by_repo") or {}).get(repo) or []) + list(
        (working.get("inbox_issues_by_repo") or {}).get(repo) or []
    )
    excluded = excluded_numbers(dict(prepared.get("stuck") or {}), repo)
    covered = issue_numbers_covered_by_prs(
        list((working.get("prs_by_repo") or {}).get(repo) or []),
        branch_prefix=prefix,
    )
    implementable = implementable_rows(raw, covered=covered, blocked=excluded)
    blocked = [
        row
        for row in raw
        if isinstance(row, dict) and int(row.get("number", -1)) in excluded
    ]
    self_id = str(prepared.get("self_repo") or self_repo())
    product_queue = bool(prepared.get("product_queue")) or product_candidates(
        ready_by_repo=work,
        prs_by_repo=working.get("prs_by_repo"),
        self_id=self_id,
    )
    if repo in set(prepared.get("skipped_repos") or []):
        reason = "outside_scope"
    elif product_queue and is_oil_repo(repo, self_id=self_id):
        reason = "product_lane"
    elif repo in set(working.get("pr_survey_failed") or []):
        reason = "pr_survey_failed"
    elif any(
        not is_manual_pr(pr)
        for pr in list((working.get("prs_by_repo") or {}).get(repo) or [])
    ):
        reason = "actionable_pr"
    elif repo in {
        str(x)
        for x in list(working.get("occupied_repos") or [])
        + list(working.get("merged_this_pass") or [])
        + list(working.get("live_issue_to_pr_repos") or [])
    }:
        reason = "occupied"
    elif not implementable:
        reason = "stuck_or_no_ready" if blocked else "no_ready"
    elif not prepared.get("executor_enabled"):
        reason = "executor_disabled"
    else:
        return {
            "ok": True,
            "route": "eligible",
            "repo": repo,
            "slot": selected["slot"],
            "implementable": implementable,
            "blocked": blocked,
        }
    return {
        "ok": True,
        "route": "ineligible",
        "repo": repo,
        "slot": selected["slot"],
        "reason": reason,
        "implementable": implementable,
        "blocked": blocked,
    }
