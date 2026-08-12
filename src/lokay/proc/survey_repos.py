"""One job: survey all managed repos (PRs, inbox, ready) into the pass workspace."""

from __future__ import annotations

import argparse
from typing import Any

from lokay.envelope import emit_exit, err, ok
from lokay.passkit import io as pass_io
from lokay.passkit.support import is_manual_pr, run_proc
from lokay.proc import label_issue as p_label
from lokay.proc import list_inbox as p_list_inbox
from lokay.proc import list_issues as p_list_issues
from lokay.proc import list_prs as p_list_prs
from lokay.proc._common import add_config_live
from lokay.stuck import excluded_numbers, issue_numbers_covered_by_prs


def run_survey_repos(*, pass_dir: str, config_path: str | None, live: bool) -> dict[str, Any]:
    begin = pass_io.read_json(pass_io.begin_path(pass_dir))
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    cfg_flag = ["--config", config_path] if config_path else []
    live_flag = ["--live"] if live else []
    actions: list[dict[str, Any]] = list(working.get("actions") or [])
    progress = int(working.get("progress") or 0)
    stuck = dict(working.get("stuck") or begin.get("stuck") or {})
    branch_prefix = str(begin.get("branch_prefix") or "ai/fix/")
    ready_label = str(begin.get("ready_label") or "ai:ready")

    prs_by_repo: dict[str, list[dict[str, Any]]] = {}
    inbox_by_repo: dict[str, int] = {}
    ready_by_repo: dict[str, list[dict[str, Any]]] = {}
    pr_survey_failed: set[str] = set()
    inbox_survey_failed: set[str] = set()
    ready_survey_failed: set[str] = set()
    remaining_inbox = 0
    remaining_ready = 0
    remaining_ready_with_pr = 0
    remaining_prs = 0
    actionable_prs = 0
    manual_prs = 0
    survey_errors = 0

    for repo_name in list(begin.get("repos") or []):
        prs = run_proc(p_list_prs.main, [*cfg_flag, "--repo", repo_name])
        actions.append({"step": "list_prs", "repo": repo_name, **prs})
        if not prs.get("ok"):
            survey_errors += 1
            pr_survey_failed.add(repo_name)
            prs_by_repo[repo_name] = []
            continue
        pr_list = list(prs.get("prs") or [])
        prs_by_repo[repo_name] = pr_list
        remaining_prs += len(pr_list)
        actionable_prs += sum(not is_manual_pr(pr) for pr in pr_list)
        manual_prs += sum(is_manual_pr(pr) for pr in pr_list)

    for repo_name in list(begin.get("repos") or []):
        listed = run_proc(p_list_inbox.main, [*cfg_flag, "--repo", repo_name])
        actions.append({"step": "list_inbox", "repo": repo_name, **listed})
        if not listed.get("ok"):
            survey_errors += 1
            inbox_survey_failed.add(repo_name)
            inbox_by_repo[repo_name] = 0
            continue
        inbox = list(listed.get("issues") or [])
        inbox_by_repo[repo_name] = len(inbox)
        remaining_inbox += len(inbox)
        # Inbox issue bodies stay in actions for plan_pass triage selection.
        working.setdefault("inbox_issues_by_repo", {})[repo_name] = inbox

    for repo_name in list(begin.get("repos") or []):
        listed = run_proc(p_list_issues.main, [*cfg_flag, "--repo", repo_name])
        actions.append({"step": "list_issues", "repo": repo_name, **listed})
        if not listed.get("ok"):
            survey_errors += 1
            ready_survey_failed.add(repo_name)
            ready_by_repo[repo_name] = []
            continue
        issues = list(listed.get("issues") or [])
        covered = issue_numbers_covered_by_prs(
            prs_by_repo.get(repo_name) or [],
            branch_prefix=branch_prefix,
        )
        skip = excluded_numbers(stuck, repo_name) | covered
        if covered:
            actions.append(
                {
                    "step": "skip_ready_with_open_pr",
                    "repo": repo_name,
                    "issues": sorted(covered),
                }
            )
            covered_ready = [i for i in issues if int(i.get("number", -1)) in covered]
            remaining_ready_with_pr += len(covered_ready)
            # Live: drop ai:ready so PR triage owns the work (no re-implement).
            if live and covered_ready:
                for issue in covered_ready:
                    num = int(issue["number"])
                    unlab = run_proc(
                        p_label.main,
                        [
                            *cfg_flag,
                            *live_flag,
                            "--repo",
                            repo_name,
                            "--issue",
                            str(num),
                            "--label",
                            ready_label,
                            "--remove",
                        ],
                    )
                    actions.append(
                        {
                            "step": "unready_with_open_pr",
                            "repo": repo_name,
                            "issue": num,
                            **unlab,
                        }
                    )
                    if unlab.get("ok") and unlab.get("applied"):
                        progress += 1
                        remaining_ready_with_pr = max(0, remaining_ready_with_pr - 1)
        if excluded_numbers(stuck, repo_name):
            actions.append(
                {
                    "step": "skip_stuck",
                    "repo": repo_name,
                    "exclude": sorted(excluded_numbers(stuck, repo_name)),
                }
            )
        implementable = [i for i in issues if int(i.get("number", -1)) not in skip]
        ready_by_repo[repo_name] = implementable
        remaining_ready += len(implementable)

    survey = {
        "prs_by_repo": prs_by_repo,
        "inbox_by_repo": inbox_by_repo,
        "inbox_issues_by_repo": dict(working.get("inbox_issues_by_repo") or {}),
        "ready_by_repo": ready_by_repo,
        "pr_survey_failed": sorted(pr_survey_failed),
        "inbox_survey_failed": sorted(inbox_survey_failed),
        "ready_survey_failed": sorted(ready_survey_failed),
        "remaining_inbox": remaining_inbox,
        "remaining_ready": remaining_ready,
        "remaining_ready_with_pr": remaining_ready_with_pr,
        "remaining_prs": remaining_prs,
        "actionable_prs": actionable_prs,
        "manual_prs": manual_prs,
        "survey_errors": survey_errors,
    }
    pass_io.write_json(pass_io.survey_path(pass_dir), survey)
    working.update(
        {
            "actions": actions,
            "progress": progress,
            "prs_by_repo": prs_by_repo,
            "inbox_by_repo": inbox_by_repo,
            "ready_by_repo": ready_by_repo,
            "pr_survey_failed": sorted(pr_survey_failed),
            "inbox_survey_failed": sorted(inbox_survey_failed),
            "ready_survey_failed": sorted(ready_survey_failed),
            "remaining_inbox": remaining_inbox,
            "remaining_ready": remaining_ready,
            "remaining_ready_with_pr": remaining_ready_with_pr,
            "remaining_prs": remaining_prs,
            "actionable_prs": actionable_prs,
            "manual_prs": manual_prs,
            "survey_errors": survey_errors,
            "stuck": stuck,
        }
    )
    pass_io.write_json(pass_io.working_path(pass_dir), working)
    return ok(
        pass_dir=pass_dir,
        survey_errors=survey_errors,
        remaining_inbox=remaining_inbox,
        remaining_ready=remaining_ready,
        remaining_prs=remaining_prs,
        actionable_prs=actionable_prs,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-survey-repos")
    add_config_live(parser)
    parser.add_argument("--pass-dir", required=True)
    args = parser.parse_args(argv)
    if not args.pass_dir:
        return emit_exit(err("pass-dir required"))
    return emit_exit(
        run_survey_repos(
            pass_dir=str(args.pass_dir),
            config_path=args.config,
            live=bool(args.live),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
