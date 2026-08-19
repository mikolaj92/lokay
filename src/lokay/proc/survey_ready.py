"""One job: list implementable ready issues; skip those covered by open AI PRs."""

from __future__ import annotations

import argparse
from typing import Any


WORK_READY_LABEL = "work:ready"

from lokay.envelope import emit_exit, err, ok
from lokay.passkit import io as pass_io
from lokay.passkit.support import run_proc
from lokay.passkit.working import load_begin_working, save_begin_working
from lokay.proc import list_issues as p_list_issues
from lokay.proc import unbounded_park as p_park
from lokay.proc._common import add_config_live
from lokay.passkit.hot import survey_scope
from lokay.stuck import excluded_numbers, issue_numbers_covered_by_prs


def run_survey_ready(*, pass_dir: str, config_path: str | None, live: bool) -> dict[str, Any]:
    begin, working = load_begin_working(pass_dir)
    cfg_flag = ["--config", config_path] if config_path else []
    live_flag = ["--live"] if live else []
    actions: list[dict[str, Any]] = list(working.get("actions") or [])
    progress = int(working.get("progress") or 0)
    stuck = dict(working.get("stuck") or begin.get("stuck") or {})
    branch_prefix = str(begin.get("branch_prefix") or "ai/fix/")
    prs_by_repo = dict(working.get("prs_by_repo") or {})
    ready_by_repo: dict[str, list[dict[str, Any]]] = {}
    ready_survey_failed: list[str] = []
    remaining_ready = 0
    remaining_ready_with_pr = 0
    survey_errors = int(working.get("survey_errors") or 0)

    scope = set(survey_scope(begin) or [])
    scoped = survey_scope(begin) is not None
    for repo_name in list(begin.get("repos") or []):

        if scoped and repo_name not in scope:
            actions.append({"step": "skip_cold_repo", "repo": repo_name, "survey": "ready"})
            ready_by_repo[repo_name] = []
            continue
        listed = run_proc(p_list_issues.main, [*cfg_flag, *live_flag, "--repo", repo_name])
        actions.append({"step": "list_issues", "repo": repo_name, **listed})
        if not listed.get("ok"):
            survey_errors += 1
            ready_survey_failed.append(repo_name)
            ready_by_repo[repo_name] = []
            continue
        issues = list(listed.get("issues") or [])
        work_ready = [
            issue
            for issue in issues
            if isinstance(issue.get("labels"), list)
            and WORK_READY_LABEL in issue["labels"]
        ]
        covered = issue_numbers_covered_by_prs(
            prs_by_repo.get(repo_name) or [],
            branch_prefix=branch_prefix,
        )
        excluded = excluded_numbers(stuck, repo_name)
        skip = excluded | covered
        if covered:
            actions.append(
                {
                    "step": "skip_ready_with_open_pr",
                    "repo": repo_name,
                    "issues": sorted(covered),
                }
            )
            covered_ready = [i for i in work_ready if int(i.get("number", -1)) in covered]
            remaining_ready_with_pr += len(covered_ready)
        blocked_ready = [
            issue for issue in work_ready if int(issue.get("number", -1)) in excluded
        ]
        if excluded:
            actions.append(
                {
                    "step": "skip_stuck",
                    "repo": repo_name,
                    "exclude": sorted(excluded),
                }
            )
        for issue in blocked_ready:
            number = int(issue["number"])
            park_argv = ["--repo", repo_name, "--issue", str(number)]
            if not live:
                park_argv.append("--dry-run")
            parked = run_proc(p_park.main, park_argv)
            actions.append(
                {
                    "step": "park_stuck",
                    "repo": repo_name,
                    "issue": number,
                    **parked,
                }
            )
            if parked.get("ok") and parked.get("applied"):
                progress += 1
        implementable = [i for i in work_ready if int(i.get("number", -1)) not in skip]
        ready_by_repo[repo_name] = implementable
        remaining_ready += len(implementable)

    survey = {
        "prs_by_repo": prs_by_repo,
        "inbox_by_repo": dict(working.get("inbox_by_repo") or {}),
        "inbox_issues_by_repo": dict(working.get("inbox_issues_by_repo") or {}),
        "ready_by_repo": ready_by_repo,
        "pr_survey_failed": list(working.get("pr_survey_failed") or []),
        "inbox_survey_failed": list(working.get("inbox_survey_failed") or []),
        "ready_survey_failed": sorted(ready_survey_failed),
        "remaining_inbox": int(working.get("remaining_inbox") or 0),
        "remaining_ready": remaining_ready,
        "remaining_ready_with_pr": remaining_ready_with_pr,
        "remaining_prs": int(working.get("remaining_prs") or 0),
        "actionable_prs": int(working.get("actionable_prs") or 0),
        "manual_prs": int(working.get("manual_prs") or 0),
        "survey_errors": survey_errors,
    }
    pass_io.write_json(pass_io.survey_path(pass_dir), survey)
    working.update(
        {
            "actions": actions,
            "progress": progress,
            "ready_by_repo": ready_by_repo,
            "ready_survey_failed": sorted(ready_survey_failed),
            "remaining_ready": remaining_ready,
            "remaining_ready_with_pr": remaining_ready_with_pr,
            "survey_errors": survey_errors,
            "stuck": stuck,
        }
    )
    save_begin_working(pass_dir, begin, working)
    return ok(
        pass_dir=pass_dir,
        remaining_ready=remaining_ready,
        survey_errors=survey_errors,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-survey-ready")
    add_config_live(parser)
    parser.add_argument("--pass-dir", required=True)
    args = parser.parse_args(argv)
    if not args.pass_dir:
        return emit_exit(err("pass-dir required"))
    return emit_exit(
        run_survey_ready(
            pass_dir=str(args.pass_dir),
            config_path=args.config,
            live=bool(args.live),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
