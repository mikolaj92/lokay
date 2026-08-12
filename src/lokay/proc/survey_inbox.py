"""One job: list undecided inbox issues for every managed repo."""

from __future__ import annotations

import argparse
from typing import Any

from lokay.envelope import emit_exit, err, ok
from lokay.passkit.support import run_proc
from lokay.passkit.working import load_begin_working, save_begin_working
from lokay.proc import list_inbox as p_list_inbox
from lokay.proc._common import add_config_live


def run_survey_inbox(*, pass_dir: str, config_path: str | None, live: bool) -> dict[str, Any]:
    del live  # read-only survey
    begin, working = load_begin_working(pass_dir)
    cfg_flag = ["--config", config_path] if config_path else []
    actions: list[dict[str, Any]] = list(working.get("actions") or [])
    inbox_by_repo: dict[str, int] = {}
    inbox_issues_by_repo: dict[str, list[dict[str, Any]]] = {}
    inbox_survey_failed: list[str] = []
    remaining_inbox = 0
    survey_errors = int(working.get("survey_errors") or 0)

    for repo_name in list(begin.get("repos") or []):
        listed = run_proc(p_list_inbox.main, [*cfg_flag, "--repo", repo_name])
        actions.append({"step": "list_inbox", "repo": repo_name, **listed})
        if not listed.get("ok"):
            survey_errors += 1
            inbox_survey_failed.append(repo_name)
            inbox_by_repo[repo_name] = 0
            inbox_issues_by_repo[repo_name] = []
            continue
        inbox = list(listed.get("issues") or [])
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
