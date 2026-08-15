"""One job: build remaining counters + honest mill health from pass workspace."""

from __future__ import annotations

import argparse
from typing import Any

from lokay.envelope import emit_exit, err, ok
from lokay.passkit import io as pass_io
from lokay.passkit.health import health_payload
from lokay.passkit.support import is_manual_pr
from lokay.proc._common import add_config_live
from lokay.proc.detach_issue_to_pr import live_issue_to_pr_receipts


def run_compute_health(*, pass_dir: str) -> dict[str, Any]:
    begin = pass_io.read_json(pass_io.begin_path(pass_dir))
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    live = bool(begin.get("live"))
    prs_by_repo = dict(working.get("prs_by_repo") or {})
    ready_by_repo = dict(working.get("ready_by_repo") or {})
    inbox_by_repo = dict(working.get("inbox_by_repo") or {})
    pr_survey_failed = set(working.get("pr_survey_failed") or [])
    inbox_survey_failed = set(working.get("inbox_survey_failed") or [])
    ready_survey_failed = set(working.get("ready_survey_failed") or [])

    by_repo: list[dict[str, Any]] = []
    for repo_name in list(begin.get("repos") or []):
        pr_list = list(prs_by_repo.get(repo_name) or [])
        ready_list = list(ready_by_repo.get(repo_name) or [])
        by_repo.append(
            {
                "repo": repo_name,
                "inbox": int(inbox_by_repo.get(repo_name) or 0),
                "ready": len(ready_list),
                "open_ai_prs": len(pr_list),
                "actionable_open_ai_prs": sum(not is_manual_pr(pr) for pr in pr_list),
                "manual_open_ai_prs": sum(is_manual_pr(pr) for pr in pr_list),
                "survey_error": bool(
                    repo_name in pr_survey_failed
                    or repo_name in inbox_survey_failed
                    or repo_name in ready_survey_failed
                ),
            }
        )

    remaining = {
        "inbox": int(working.get("remaining_inbox") or 0),
        "ready": int(working.get("remaining_ready") or 0),
        "ready_with_open_pr": int(working.get("remaining_ready_with_pr") or 0),
        "open_ai_prs": int(working.get("remaining_prs") or 0),
        "actionable_open_ai_prs": int(working.get("actionable_prs") or 0),
        "manual_open_ai_prs": int(working.get("manual_prs") or 0),
        "intake_skip_reason": working.get("intake_skip_reason"),
        "issue_to_pr_started": max(
            int(working.get("issue_to_pr_started") or 0),
            sum(
                1
                for row in live_issue_to_pr_receipts()
                if str(row.get("repo") or "") in set(begin.get("repos") or [])
            ),
        ),
        "max_issue_to_pr_per_pass": int(begin.get("max_issue_to_pr_per_pass") or 0),
        "mergeable_green": int(working.get("mergeable_green") or 0),
        "merge_disabled": int(working.get("merge_disabled") or 0),
        "needs_repair": int(working.get("needs_repair") or 0),
        "review_limbo": int(working.get("review_limbo") or 0),
        "pending_checks": int(working.get("pending_checks") or 0),
        "no_checks_blocked": int(working.get("no_checks_blocked") or 0),
        "merge_conflicts": int(working.get("merge_conflicts") or 0),
        "blocked_this_pass": int(working.get("blocked_this_pass") or 0),
        "survey_errors": int(working.get("survey_errors") or 0),
        "by_repo": by_repo,
    }
    payload = health_payload(
        cfg_mode=str(begin.get("mode") or "dry-run"),
        live=live,
        executed=live,
        progress=int(working.get("progress") or 0),
        remaining=remaining,
        actions=list(working.get("actions") or []),
        planned=list(begin.get("planned") or []),
        stuck_path=str(begin.get("stuck_path") or "") or None,
        executor_enabled=bool(begin.get("executor_enabled")),
        merge_enabled=bool(begin.get("merge_enabled")),
    )
    pass_io.write_json(pass_io.tick_path(pass_dir), payload)
    # Domain health is data for the mill; effector itself succeeds for conduction.
    return ok(
        pass_dir=pass_dir,
        health=payload.get("health"),
        progress=payload.get("progress"),
        idle=payload.get("idle"),
        tick_ok=bool(payload.get("ok")),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-compute-health")
    add_config_live(parser)
    parser.add_argument("--pass-dir", required=True)
    args = parser.parse_args(argv)
    if not args.pass_dir:
        return emit_exit(err("pass-dir required"))
    return emit_exit(run_compute_health(pass_dir=str(args.pass_dir)))


if __name__ == "__main__":
    raise SystemExit(main())
