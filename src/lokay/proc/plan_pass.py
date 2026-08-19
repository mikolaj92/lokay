"""One job: select triage targets + closeout set + provisional implement candidates."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from lokay.envelope import emit_exit, err, ok
from lokay.passkit import io as pass_io
from lokay.passkit.support import is_manual_pr
from lokay.proc._common import add_config_live
from lokay.stuck import is_blocked_in_ledger, load_stuck


def run_plan_pass(*, pass_dir: str) -> dict[str, Any]:
    begin = pass_io.read_json(pass_io.begin_path(pass_dir))
    survey = pass_io.read_json(pass_io.survey_path(pass_dir))
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    live = bool(begin.get("live"))
    triage_budget = int(begin.get("triage_budget") or 0)
    actions: list[dict[str, Any]] = list(working.get("actions") or [])
    stuck_path = str(begin.get("stuck_path") or "")
    stuck = (
        load_stuck(Path(stuck_path))
        if stuck_path
        else dict(working.get("stuck") or {})
    )

    triage_targets: list[dict[str, Any]] = []
    closeout_targets: list[dict[str, Any]] = []
    implement_candidates: list[dict[str, Any]] = []

    prs_by_repo = dict(survey.get("prs_by_repo") or {})
    inbox_issues = dict(survey.get("inbox_issues_by_repo") or {})
    ready_by_repo = dict(survey.get("ready_by_repo") or {})
    pr_survey_failed = set(survey.get("pr_survey_failed") or [])

    # Triage: per-repo PR-first; skip receipts when survey failed or actionable AI PR.
    # Skip actions are recorded whenever live (even if triage_budget is already 0).
    if live:
        for repo_name in list(begin.get("repos") or []):
            inbox = list(inbox_issues.get(repo_name) or [])
            if not inbox:
                continue
            if repo_name in pr_survey_failed:
                actions.append(
                    {
                        "step": "skip_inbox_triage_survey_failed",
                        "repo": repo_name,
                        "count": len(inbox),
                        "reason": "PR survey failed closed for this repo; refuse inbox triage",
                    }
                )
                continue
            repo_actionable = sum(
                not is_manual_pr(pr) for pr in (prs_by_repo.get(repo_name) or [])
            )
            if repo_actionable:
                actions.append(
                    {
                        "step": "skip_inbox_triage_repo_backpressure",
                        "repo": repo_name,
                        "count": len(inbox),
                        "actionable_open_ai_prs": repo_actionable,
                        "reason": (
                            f"per-repo PR-first: {repo_actionable} actionable AI PR(s) "
                            "in this repo block inbox triage"
                        ),
                    }
                )
                continue
            for issue in inbox:
                issue_number = int(issue["number"])
                if is_blocked_in_ledger(stuck, repo_name, issue_number):
                    actions.append(
                        {
                            "step": "skip_inbox_triage_stuck_blocked",
                            "repo": repo_name,
                            "issue": issue_number,
                            "ok": True,
                            "skipped": True,
                            "blocked": True,
                            "reason": "blocked_in_stuck_ledger",
                        }
                    )
                    continue
                if triage_budget <= 0:
                    break
                triage_targets.append({"repo": repo_name, "issue": issue_number})
                triage_budget -= 1

    # Closeout: every open AI PR (manual skipped at dispatch with a receipt).
    for repo_name in list(begin.get("repos") or []):
        for pr in list(prs_by_repo.get(repo_name) or []):
            closeout_targets.append(
                {
                    "repo": repo_name,
                    "pr": int(pr["number"]),
                    "head_ref": str(pr.get("head_ref") or ""),
                    "mergeable": str(pr.get("mergeable") or ""),
                    "manual": is_manual_pr(pr),
                    "labels": list(pr.get("labels") or [])
                    if isinstance(pr.get("labels"), list)
                    else pr.get("labels"),
                    "title": str(pr.get("title") or ""),
                }
            )

    # Provisional implement candidates (final select_implement re-checks after closeout).
    for repo_name in list(begin.get("repos") or []):
        for issue in list(ready_by_repo.get(repo_name) or []):
            implement_candidates.append(
                {
                    "repo": repo_name,
                    "number": int(issue.get("number")),
                    "title": str(issue.get("title") or ""),
                }
            )

    plan = {
        "triage_targets": triage_targets,
        "closeout_targets": closeout_targets,
        "implement_candidates": implement_candidates,
        "triage_budget_remaining": triage_budget,
    }
    pass_io.write_json(pass_io.plan_path(pass_dir), plan)
    working["actions"] = actions
    pass_io.write_json(pass_io.working_path(pass_dir), working)
    return ok(
        pass_dir=pass_dir,
        triage_count=len(triage_targets),
        closeout_count=len(closeout_targets),
        implement_candidate_count=len(implement_candidates),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-plan-pass")
    add_config_live(parser)
    parser.add_argument("--pass-dir", required=True)
    args = parser.parse_args(argv)
    if not args.pass_dir:
        return emit_exit(err("pass-dir required"))
    return emit_exit(run_plan_pass(pass_dir=str(args.pass_dir)))


if __name__ == "__main__":
    raise SystemExit(main())
