"""One job: list undecided inbox issues for every managed repo."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from lokay.envelope import emit_exit, err, ok
from lokay.passkit.support import run_proc
from lokay.passkit.working import load_begin_working, save_begin_working
from lokay.proc import list_inbox as p_list_inbox
from lokay.proc._common import add_config_live
from lokay.passkit.hot import survey_scope
from lokay.stuck import is_blocked_in_ledger, load_stuck


MINI_MILL_REPO = "mikolaj92/lokay"


def run_survey_inbox(*, pass_dir: str, config_path: str | None, live: bool) -> dict[str, Any]:
    live_flag = ["--live"] if live else []
    begin, working = load_begin_working(pass_dir)
    cfg_flag = ["--config", config_path] if config_path else []
    actions: list[dict[str, Any]] = list(working.get("actions") or [])
    inbox_by_repo: dict[str, int] = {}
    inbox_issues_by_repo: dict[str, list[dict[str, Any]]] = {}
    inbox_survey_failed: list[str] = []
    remaining_inbox = 0
    survey_errors = int(working.get("survey_errors") or 0)
    stuck_path = str(begin.get("stuck_path") or "")
    stuck = (
        load_stuck(Path(stuck_path))
        if stuck_path
        else dict(working.get("stuck") or begin.get("stuck") or {})
    )

    scope = set(survey_scope(begin) or [])
    scoped = survey_scope(begin) is not None
    repos = list(begin.get("repos") or [])
    lokay_mill = MINI_MILL_REPO in repos
    for repo_name in repos:
        if lokay_mill and repo_name != MINI_MILL_REPO:
            actions.append(
                {
                    "step": "skip_inbox_survey_outside_mini_scope",
                    "repo": repo_name,
                    "reason": f"mini mill only surveys inbox for {MINI_MILL_REPO}",
                }
            )
            inbox_by_repo[repo_name] = 0
            inbox_issues_by_repo[repo_name] = []
            continue
        if scoped and repo_name not in scope:
            actions.append({"step": "skip_cold_repo", "repo": repo_name, "survey": "inbox"})
            inbox_by_repo[repo_name] = 0
            inbox_issues_by_repo[repo_name] = []
            continue
        listed = run_proc(p_list_inbox.main, [*cfg_flag, *live_flag, "--repo", repo_name])
        actions.append({"step": "list_inbox", "repo": repo_name, **listed})
        if not listed.get("ok"):
            survey_errors += 1
            inbox_survey_failed.append(repo_name)
            inbox_by_repo[repo_name] = 0
            inbox_issues_by_repo[repo_name] = []
            continue
        inbox: list[dict[str, Any]] = []
        blocked_numbers: list[int] = []
        for issue in list(listed.get("issues") or []):
            number = int(issue.get("number", -1))
            if is_blocked_in_ledger(stuck, repo_name, number):
                blocked_numbers.append(number)
                continue
            inbox.append(issue)
        if blocked_numbers:
            actions.append(
                {
                    "step": "skip_inbox_stuck_blocked",
                    "repo": repo_name,
                    "issues": blocked_numbers,
                }
            )
        inbox_by_repo[repo_name] = len(inbox)
        inbox_issues_by_repo[repo_name] = inbox
        remaining_inbox += len(inbox)

    working.update(
        {
            "actions": actions,
            "inbox_by_repo": inbox_by_repo,
            "inbox_issues_by_repo": inbox_issues_by_repo,
            "inbox_survey_failed": sorted(inbox_survey_failed),
            "remaining_inbox": remaining_inbox,
            "survey_errors": survey_errors,
        }
    )
    save_begin_working(pass_dir, begin, working)
    return ok(
        pass_dir=pass_dir,
        remaining_inbox=remaining_inbox,
        survey_errors=survey_errors,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-survey-inbox")
    add_config_live(parser)
    parser.add_argument("--pass-dir", required=True)
    args = parser.parse_args(argv)
    if not args.pass_dir:
        return emit_exit(err("pass-dir required"))
    return emit_exit(
        run_survey_inbox(
            pass_dir=str(args.pass_dir),
            config_path=args.config,
            live=bool(args.live),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
