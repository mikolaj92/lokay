"""One job: kill detached issue_to_pr past pi_budget so occupy cannot last 40 min."""

from __future__ import annotations

import argparse
from typing import Any

from lokay.envelope import emit_exit, err, ok
from lokay.proc._common import add_config_live
from lokay.proc.detach_issue_to_pr import (
    issue_to_pr_receipt_path,
    live_issue_to_pr_receipts,
    terminate_issue_to_pr_pid,
)
from lokay.proc.pi_budget import DEFAULT_BUDGET_S, check_pi_budget


def run_reap_over_budget(*, budget_s: int = DEFAULT_BUDGET_S) -> dict[str, Any]:
    reaped: list[dict[str, Any]] = []
    kept: list[dict[str, Any]] = []
    for row in live_issue_to_pr_receipts():
        repo = str(row.get("repo") or "")
        try:
            issue = int(row.get("issue"))
            pid = int(row.get("pid"))
        except (TypeError, ValueError):
            continue
        if pid <= 0 or not repo:
            continue
        check = check_pi_budget(pid, budget_s)
        elapsed = float(check.get("elapsed_s") or 0)
        if not check.get("over_budget"):
            kept.append(
                {"repo": repo, "issue": issue, "pid": pid, "elapsed_s": elapsed}
            )
            continue
        killed = terminate_issue_to_pr_pid(pid)
        path = issue_to_pr_receipt_path(repo, issue)
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        reaped.append(
            {
                "repo": repo,
                "issue": issue,
                "pid": pid,
                "elapsed_s": elapsed,
                "budget_s": budget_s,
                "killed": killed,
            }
        )
    return ok(
        reaped=reaped,
        kept=kept,
        reaped_count=len(reaped),
        budget_s=budget_s,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-reap-over-budget")
    add_config_live(parser)
    parser.add_argument("--pass-dir", default="")
    parser.add_argument("--budget", type=int, default=DEFAULT_BUDGET_S)
    args = parser.parse_args(argv)
    if args.budget < 0:
        return emit_exit(err("budget must be >= 0", budget_s=args.budget))
    payload = run_reap_over_budget(budget_s=int(args.budget))
    payload["pass_dir"] = str(args.pass_dir or "")
    return emit_exit(payload)


if __name__ == "__main__":
    raise SystemExit(main())
