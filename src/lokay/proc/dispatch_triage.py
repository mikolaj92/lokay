"""One job: run planned inbox triage child paths (issue_triage)."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from lokay.envelope import emit_exit, err, ok
from lokay.graph_run import run_path
from lokay.passkit import io as pass_io
from lokay.proc._common import add_config_live
from lokay.stuck import is_blocked_in_ledger, load_stuck
from lokay.mill_scope import SKIP_REASON, in_scope, mill_repo

MINI_MILL_REPO = mill_repo()
_REPO_SKIP_REASON = SKIP_REASON


def run_dispatch_triage(*, pass_dir: str, config_path: str | None, live: bool) -> dict[str, Any]:
    plan = pass_io.read_json(pass_io.plan_path(pass_dir))
    begin = pass_io.read_json(pass_io.begin_path(pass_dir))
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    actions: list[dict[str, Any]] = list(working.get("actions") or [])
    stuck_path = str(begin.get("stuck_path") or "")
    stuck = load_stuck(Path(stuck_path)) if stuck_path else dict(working.get("stuck") or {})
    progress = int(working.get("progress") or 0)
    remaining_inbox = int(working.get("remaining_inbox") or 0)
    inbox_by_repo = dict(working.get("inbox_by_repo") or {})
    ran = 0
    skipped_repos: list[str] = []

    if not live:
        pass_io.write_json(pass_io.working_path(pass_dir), working)
        return ok(pass_dir=pass_dir, ran=0, skipped=True, reason="dry_run")

    for target in list(plan.get("triage_targets") or []):
        repo_name = str(target["repo"])
        num = int(target["issue"])
        if not in_scope(repo_name, begin.get("repos") or [], mill=MINI_MILL_REPO):
            if repo_name not in skipped_repos:
                skipped_repos.append(repo_name)
            actions.append(
                {
                    "step": "skip_repo_outside_mini_mill",
                    "repo": repo_name,
                    "issue": num,
                    "ok": True,
                    "skipped": True,
                    "reason": _REPO_SKIP_REASON,
                }
            )
            continue
        if is_blocked_in_ledger(stuck, repo_name, num):
            actions.append(
                {
                    "step": "skip_stuck",
                    "action": "issue_triage",
                    "repo": repo_name,
                    "issue": num,
                    "ok": True,
                    "skipped": True,
                    "blocked": True,
                    "reason": "blocked_in_stuck_ledger",
                }
            )
            continue
        try:
            tri = run_path(
                path_id="issue_triage",
                repo=repo_name,
                issue=num,
                config_path=config_path,
                live=True,
            )
            actions.append(
                {"step": "issue_triage", "repo": repo_name, "issue": num, **tri}
            )
            # Live progress means a real label mutation, never merely a
            # successfully completed graph or a decision=skip no-op.
            decision = tri.get("decision")
            skipped = (
                tri.get("skipped")
                or (
                    isinstance(decision, dict)
                    and decision.get("decision") == "skip"
                )
            )
            if tri.get("ok") and tri.get("applied") is True and not skipped:
                progress += 1
                remaining_inbox = max(0, remaining_inbox - 1)
                inbox_by_repo[repo_name] = max(
                    0, int(inbox_by_repo.get(repo_name) or 0) - 1
                )
            ran += 1
        except Exception as exc:
            actions.append(
                {
                    "step": "issue_triage",
                    "repo": repo_name,
                    "issue": num,
                    "ok": False,
                    "engine": "fala",
                    "error": f"Fala path failed (no atom super-fallback): {exc}",
                }
            )
            ran += 1

    working.update(
        {
            "actions": actions,
            "progress": progress,
            "remaining_inbox": remaining_inbox,
            "inbox_by_repo": inbox_by_repo,
        }
    )
    pass_io.write_json(pass_io.working_path(pass_dir), working)
    result = ok(pass_dir=pass_dir, ran=ran)
    if skipped_repos:
        result.update(
            skipped=True,
            reason=_REPO_SKIP_REASON,
            skipped_repos=skipped_repos,
        )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-dispatch-triage")
    add_config_live(parser)
    parser.add_argument("--pass-dir", required=True)
    args = parser.parse_args(argv)
    if not args.pass_dir:
        return emit_exit(err("pass-dir required"))
    return emit_exit(
        run_dispatch_triage(
            pass_dir=str(args.pass_dir),
            config_path=args.config,
            live=bool(args.live),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
