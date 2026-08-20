"""One job: list open AI PRs for every managed repo into the pass workspace."""

from __future__ import annotations

import argparse
from typing import Any

from lokay.envelope import emit_exit, err, ok
from lokay.passkit.support import is_manual_pr, run_proc
from lokay.passkit.working import load_begin_working, save_begin_working
from lokay.proc import list_prs as p_list_prs
from lokay.proc._common import add_config_live
from lokay.passkit.hot import survey_scope
from lokay.mill_scope import mill_repo, scoped_repos


MINI_MILL_REPO = mill_repo()


def run_survey_prs(*, pass_dir: str, config_path: str | None, live: bool) -> dict[str, Any]:
    live_flag = ["--live"] if live else []
    begin, working = load_begin_working(pass_dir)
    cfg_flag = ["--config", config_path] if config_path else []
    actions: list[dict[str, Any]] = list(working.get("actions") or [])
    prs_by_repo: dict[str, list[dict[str, Any]]] = {}
    pr_survey_failed: list[str] = []
    remaining_prs = 0
    actionable_prs = 0
    manual_prs = 0
    survey_errors = int(working.get("survey_errors") or 0)

    scope = set(survey_scope(begin) or [])
    scoped = survey_scope(begin) is not None
    repos = list(begin.get("repos") or [])
    _, skipped_repos = scoped_repos(repos, mill=MINI_MILL_REPO)
    skipped = set(skipped_repos)
    for repo_name in repos:
        if repo_name in skipped:
            actions.append(
                {
                    "step": "skip_pr_survey_outside_mini_scope",
                    "repo": repo_name,
                    "reason": f"mini mill only surveys PRs for {MINI_MILL_REPO}",
                }
            )
            prs_by_repo[repo_name] = []
            continue
        if scoped and repo_name not in scope:
            actions.append({"step": "skip_cold_repo", "repo": repo_name, "survey": "prs"})
            prs_by_repo[repo_name] = []
            continue
        prs = run_proc(p_list_prs.main, [*cfg_flag, *live_flag, "--repo", repo_name])
        actions.append({"step": "list_prs", "repo": repo_name, **prs})
        if not prs.get("ok"):
            survey_errors += 1
            pr_survey_failed.append(repo_name)
            prs_by_repo[repo_name] = []
            continue
        pr_list = list(prs.get("prs") or [])
        prs_by_repo[repo_name] = pr_list
        remaining_prs += len(pr_list)
        actionable_prs += sum(not is_manual_pr(pr) for pr in pr_list)
        manual_prs += sum(is_manual_pr(pr) for pr in pr_list)

    working.update(
        {
            "actions": actions,
            "prs_by_repo": prs_by_repo,
            "pr_survey_failed": sorted(pr_survey_failed),
            "remaining_prs": remaining_prs,
            "actionable_prs": actionable_prs,
            "manual_prs": manual_prs,
            "survey_errors": survey_errors,
        }
    )
    save_begin_working(pass_dir, begin, working)
    return ok(
        pass_dir=pass_dir,
        remaining_prs=remaining_prs,
        actionable_prs=actionable_prs,
        survey_errors=survey_errors,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-survey-prs")
    add_config_live(parser)
    parser.add_argument("--pass-dir", required=True)
    args = parser.parse_args(argv)
    if not args.pass_dir:
        return emit_exit(err("pass-dir required"))
    return emit_exit(
        run_survey_prs(
            pass_dir=str(args.pass_dir),
            config_path=args.config,
            live=bool(args.live),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
