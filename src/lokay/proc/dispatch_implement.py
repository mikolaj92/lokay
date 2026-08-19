"""One job: intake gate + detach up to K issue_to_pr (one per repo, parallel)."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from lokay.pass_receipt import build_pass_receipt, write_pass_receipt
from lokay.envelope import emit_exit, err, ok
from lokay.passkit import io as pass_io
from lokay.passkit.support import run_proc, run_select
from lokay.proc import intake_issue as p_intake
from lokay.proc import label_issue as p_label
from lokay.proc import select_issue as p_select
from lokay.proc import close_issue as p_close
from lokay.proc import unbounded_park as p_park
from lokay.proc._common import add_config_live
from lokay.proc.detach_issue_to_pr import (
    detach_issue_to_pr,
    has_unreadable_issue_to_pr_receipts,
)
from lokay.proc.repo_mutex import inspect_mutex, _live_ps_text
from lokay.stuck import clear_issue, excluded_numbers, record_failure, save_stuck

# In-process hook for compose_tick tests. Production / Fala leave this None
# and detach. Tick binds a patched composer only when tests replace it.
compose_issue_to_pr = None

MINI_MILL_REPO = "mikolaj92/lokay"
_REPO_SKIP_REASON = "repo_not_delivered_by_mini_mill"


def _is_plan_only_failure(result: dict[str, Any]) -> bool:
    """Recognize the terminal no-code result in either envelope field."""
    return any(
        str(result.get(field) or "").strip() == "plan_only"
        for field in ("error", "reason")
    )


def run_dispatch_implement(*, pass_dir: str, config_path: str | None, live: bool) -> dict[str, Any]:
    begin = pass_io.read_json(pass_io.begin_path(pass_dir))
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    implement = pass_io.read_json(pass_io.implement_path(pass_dir))
    cfg_flag = ["--config", config_path] if config_path else []
    live_flag = ["--live"] if live else []
    actions: list[dict[str, Any]] = list(working.get("actions") or [])
    progress = int(working.get("progress") or 0)
    stuck = dict(working.get("stuck") or {})
    stuck_path = Path(str(begin.get("stuck_path") or ""))
    max_fail = int(begin.get("max_fail") or 1)
    blocked_label = str(begin.get("blocked_label") or "ai:blocked")
    remaining_ready = int(working.get("remaining_ready") or 0)
    remaining_prs = int(working.get("remaining_prs") or 0)
    actionable_prs = int(working.get("actionable_prs") or 0)
    blocked_this_pass = int(working.get("blocked_this_pass") or 0)
    issue_to_pr_started = int(working.get("issue_to_pr_started") or 0)
    skipped_repos: list[str] = []
    issue_budget = int(implement.get("issue_budget") or begin.get("issue_budget") or 0)
    prs_by_repo: dict[str, list[dict[str, Any]]] = {
        k: list(v) for k, v in dict(working.get("prs_by_repo") or {}).items()
    }
    ready_by_repo: dict[str, list[dict[str, Any]]] = {
        k: list(v) for k, v in dict(working.get("ready_by_repo") or {}).items()
    }

    if not live or issue_budget <= 0:
        return ok(pass_dir=pass_dir, started=0, skipped=True, reason="dry_run")
    if has_unreadable_issue_to_pr_receipts():
        # Stale/unreadable cycle files are idle, not a catalog-wide stop.
        # Dead pid / pid 0 / failed receipts must not refuse K=1 dispatch.
        actions.append(
            {
                "step": "receipts_unreadable",
                "note": "unknown receipts treated as idle; dispatch continues",
            }
        )

    try:
        ps_text = _live_ps_text()
    except Exception as exc:  # noqa: BLE001 -- unknown mutex state must not launch a sibling
        return err(
            "cannot inspect repo mutex; refusing issue_to_pr dispatch",
            pass_dir=pass_dir,
            reason="repo_mutex_unknown",
            error_detail=str(exc),
        )
    for repo_name in list(implement.get("clean_repos") or []):
        if issue_budget <= 0:
            break
        if repo_name != MINI_MILL_REPO:
            skipped_repos.append(str(repo_name))
            actions.append(
                {
                    "step": "skip_repo_outside_mini_mill",
                    "repo": repo_name,
                    "skipped": True,
                    "reason": _REPO_SKIP_REASON,
                }
            )
            continue
        mutex = inspect_mutex(repo=str(repo_name), ps_text=ps_text)
        if mutex.get("busy"):
            actions.append({"step": "skip_repo_mutex", "repo": repo_name, "pids": mutex.get("pids")})
            continue
        implementable = list(ready_by_repo.get(repo_name) or [])
        if not implementable:
            continue
        skip = excluded_numbers(stuck, repo_name)
        # At most one issue_to_pr attempt per repo per pass (serial within repo;
        # frees remaining K budget for other clean repos).
        attempted_here = False
        while implementable and issue_budget > 0 and not attempted_here:
            sel = run_select(
                p_select.main,
                {"issues": implementable, "exclude": sorted(skip)},
            )
            actions.append({"step": "select_issue", "repo": repo_name, **sel})
            selected = sel.get("selected")
            if not selected:
                break
            num = int(selected["number"])
            gate = run_proc(
                p_intake.main,
                [
                    *cfg_flag,
                    *live_flag,
                    "--repo",
                    selected["repo"],
                    "--issue",
                    str(num),
                    "--require-ready",
                ],
            )
            actions.append(
                {
                    "step": "intake_issue",
                    "repo": selected["repo"],
                    "issue": num,
                    **gate,
                }
            )
            if gate.get("applied"):
                progress += 1
            if not (gate.get("ok") and gate.get("implementable")):
                remaining_ready = max(0, remaining_ready - 1)
                implementable = [
                    i for i in implementable if int(i.get("number", -1)) != num
                ]
                continue
            composer = compose_issue_to_pr
            if callable(composer):
                result = composer(
                    config_path=config_path,
                    repo=str(selected["repo"]),
                    issue_number=num,
                    live=True,
                )
            else:
                result = detach_issue_to_pr(
                    repo=str(selected["repo"]),
                    issue=num,
                    config_path=config_path,
                )
            actions.append({"step": "issue_to_pr", **result})
            issue_budget -= 1
            issue_to_pr_started += 1
            attempted_here = True
            if result.get("ok"):
                progress += 1
                remaining_ready = max(0, remaining_ready - 1)
                clear_issue(stuck, selected["repo"], num)
                pr_n = result.get("pr")
                br = str(result.get("branch") or "")
                if pr_n is not None and br:
                    remaining_prs += 1
                    actionable_prs += 1
                    prs_by_repo.setdefault(selected["repo"], []).append(
                        {
                            "number": int(pr_n),
                            "head_ref": br,
                            "mergeable": "UNKNOWN",
                            "title": str(
                                (selected.get("title") if isinstance(selected, dict) else "")
                                or ""
                            ),
                        }
                    )
            else:
                row = record_failure(
                    stuck,
                    repo=selected["repo"],
                    number=num,
                    error=str(
                        result.get("error") or result.get("fala") or "issue_to_pr failed"
                    ),
                    max_failures=max_fail,
                )
                # Bounded repair already ran and the suite is still red
                # (AlphaCodium K=1 exhausted): this seed is deterministically
                # stuck — block it now so the mill takes the next seed instead
                # of burning later passes on an identical failing path.
                if str(result.get("reason") or "") == "local_repair_exhausted":
                    row["blocked"] = True
                actions.append(
                    {
                        "step": "record_stuck",
                        "repo": selected["repo"],
                        "issue": num,
                        "failures": row.get("failures"),
                        "blocked": bool(row.get("blocked")),
                    }
                )
                if row.get("blocked"):
                    skip.add(num)
                    blocked_this_pass += 1
                    lab = run_proc(
                        p_label.main,
                        [
                            *cfg_flag,
                            *live_flag,
                            "--repo",
                            selected["repo"],
                            "--issue",
                            str(num),
                            "--label",
                            blocked_label,
                        ],
                    )
                    actions.append({"step": "label_blocked", **lab})
                    if lab.get("ok") and lab.get("applied"):
                        progress += 1
                        remaining_ready = max(0, remaining_ready - 1)
                    if _is_plan_only_failure(result):
                        park = run_proc(
                            p_park.main,
                            ["--repo", selected["repo"], "--issue", str(num)],
                        )
                        actions.append(
                            {
                                "step": "park_plan_only",
                                "repo": selected["repo"],
                                "issue": num,
                                **park,
                            }
                        )
                        if park.get("ok"):
                            close = run_proc(
                                p_close.main,
                                [
                                    *cfg_flag,
                                    *live_flag,
                                    "--repo",
                                    selected["repo"],
                                    "--issue",
                                    str(num),
                                    "--comment",
                                    "plan_only fail-closed",
                                ],
                            )
                            actions.append(
                                {
                                    "step": "close_plan_only",
                                    "repo": selected["repo"],
                                    "issue": num,
                                    **close,
                                }
                            )
            implementable = [i for i in implementable if int(i.get("number", -1)) != num]
        ready_by_repo[repo_name] = list(implementable)

    save_stuck(stuck_path, stuck)
    working.update(
        {
            "actions": actions,
            "progress": progress,
            "stuck": stuck,
            "prs_by_repo": prs_by_repo,
            "ready_by_repo": ready_by_repo,
            "remaining_ready": remaining_ready,
            "remaining_prs": remaining_prs,
            "actionable_prs": actionable_prs,
            "blocked_this_pass": blocked_this_pass,
            "issue_to_pr_started": issue_to_pr_started,
            "intake_skip_reason": None,
        }
    )
    pass_io.write_json(pass_io.working_path(pass_dir), working)
    try:
        state_path = Path(str(begin.get("state_path") or Path.home() / ".lokay" / "state.jsonl"))
        receipt = build_pass_receipt(
            tick={
                "ok": True,
                "health": "running",
                "progress": progress,
                "live": True,
                "remaining": {
                    "issue_to_pr_started": issue_to_pr_started,
                    "max_issue_to_pr_per_pass": int(
                        begin.get("max_issue_to_pr_per_pass") or issue_budget
                    ),
                    "ready": remaining_ready,
                    "actionable_open_ai_prs": actionable_prs,
                },
                "note": "implement detached; last-pass does not wait on pi",
            },
            merge_enabled=bool(begin.get("merge_enabled")),
            require_checks=bool(begin.get("require_checks")),
            require_llm_review=bool(begin.get("require_llm_review")),
            max_issue_to_pr_per_pass=int(begin.get("max_issue_to_pr_per_pass") or 0),
            config_path=begin.get("config_path") or config_path,
        )
        write_pass_receipt(receipt, state_path=state_path)
    except OSError:
        pass
    result = ok(
        pass_dir=pass_dir,
        started=issue_to_pr_started,
        detached=issue_to_pr_started > 0,
    )
    if skipped_repos:
        result.update(
            skipped=True,
            reason=_REPO_SKIP_REASON,
            skipped_repos=skipped_repos,
        )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-dispatch-implement")
    add_config_live(parser)
    parser.add_argument("--pass-dir", required=True)
    args = parser.parse_args(argv)
    if not args.pass_dir:
        return emit_exit(err("pass-dir required"))
    return emit_exit(
        run_dispatch_implement(
            pass_dir=str(args.pass_dir),
            config_path=args.config,
            live=bool(args.live),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
