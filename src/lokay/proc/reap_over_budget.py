"""One job: kill detached issue_to_pr past pi_budget so occupy cannot last 40 min."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from lokay.config import Config
from lokay.envelope import emit_exit, err, ok
from lokay.gh_issues import get_issue
from lokay.passkit.support import run_proc
from lokay.proc import close_issue as p_close
from lokay.proc import unbounded_park as p_park
from lokay.proc._common import add_config_live, runner
from lokay.proc.detach_issue_to_pr import (
    issue_to_pr_receipt_path,
    live_issue_to_pr_receipts,
    terminate_issue_to_pr_pid,
    wrapper_has_coding_descendant,
)
from lokay.proc.pi_budget import DEFAULT_BUDGET_S, check_pi_budget
from lokay.stuck import load_stuck, record_failure, save_stuck


def _stuck_path_for(pass_dir: str | None) -> Path:
    """Use the factory pass ledger, with the normal state-dir fallback."""
    if pass_dir:
        try:
            begin = json.loads(
                (Path(pass_dir) / "begin.json").read_text(encoding="utf-8")
            )
            configured = begin.get("stuck_path") if isinstance(begin, dict) else None
            if configured:
                return Path(str(configured))
        except (OSError, ValueError):
            pass
    return Path.home() / ".lokay" / "stuck.json"


def _issue_is_closed(repo: str, issue: int, *, live: bool) -> bool:
    """Read GitHub state before applying an immediate closed-issue reap."""
    if not live:
        return False
    try:
        current = get_issue(runner(), Config(), repo, issue, live=True)
    except Exception:  # noqa: BLE001
        # An unavailable state lookup is not evidence that a live coder is
        # obsolete. The normal budget policy below remains the fallback.
        return False
    return current is not None and current.state.upper() == "CLOSED"


def run_reap_over_budget(
    *,
    budget_s: int = DEFAULT_BUDGET_S,
    pass_dir: str | None = None,
    config_path: str | None = None,
    live: bool = False,
) -> dict[str, Any]:
    reaped: list[dict[str, Any]] = []
    kept: list[dict[str, Any]] = []
    stuck: dict[str, Any] | None = None
    stuck_path = _stuck_path_for(pass_dir)
    for row in live_issue_to_pr_receipts():
        repo = str(row.get("repo") or "")
        try:
            issue = int(row.get("issue"))
            pid = int(row.get("pid"))
        except (TypeError, ValueError):
            continue
        if pid <= 0 or not repo:
            continue
        closed = _issue_is_closed(repo, issue, live=live)
        check = check_pi_budget(pid, budget_s)
        elapsed = float(check.get("elapsed_s") or 0)
        if not closed and not check.get("over_budget"):
            kept.append(
                {"repo": repo, "issue": issue, "pid": pid, "elapsed_s": elapsed}
            )
            continue
        # Killing an over-budget wrapper while Fala/pi still codes orphans the
        # coder. A closed issue is different: its coder can no longer produce
        # a useful PR, so reap the whole process group immediately.
        if not closed and wrapper_has_coding_descendant(pid):
            kept.append(
                {
                    "repo": repo,
                    "issue": issue,
                    "pid": pid,
                    "elapsed_s": elapsed,
                    "reason": "coder_live",
                }
            )
            continue
        killed = terminate_issue_to_pr_pid(pid)
        reason = "issue_closed" if closed else "over_budget"
        path = issue_to_pr_receipt_path(repo, issue)
        # Leave the dead receipt. Unlinking it hides the child from harvest,
        # so a reaped pi vanishes with no PR and no fail-closed.
        try:
            stamped = dict(row)
            stamped.update(ok=False, reason=reason, reaped=True)
            path.write_text(json.dumps(stamped), encoding="utf-8")
        except OSError:
            pass
        result = {
            "repo": repo,
            "issue": issue,
            "pid": pid,
            "elapsed_s": elapsed,
            "budget_s": budget_s,
            "killed": killed,
            "reason": reason,
        }
        if killed and not closed:
            if stuck is None:
                stuck = load_stuck(stuck_path)
            row = record_failure(
                stuck,
                repo=repo,
                number=issue,
                error="plan_only",
                max_failures=1,
            )
            row["reason"] = "plan_only"
            save_stuck(stuck_path, stuck)
            result["park"] = run_proc(
                p_park.main,
                ["--repo", repo, "--issue", str(issue)],
            )
            if result["park"].get("ok"):
                close_argv = []
                if config_path:
                    close_argv.extend(["--config", config_path])
                if live:
                    close_argv.append("--live")
                close_argv.extend(
                    [
                        "--repo",
                        repo,
                        "--issue",
                        str(issue),
                        "--comment",
                        "plan_only fail-closed",
                    ]
                )
                result["close"] = run_proc(p_close.main, close_argv)
        reaped.append(result)
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
    payload = run_reap_over_budget(
        budget_s=int(args.budget),
        pass_dir=str(args.pass_dir or "") or None,
        config_path=args.config,
        live=bool(args.live),
    )
    payload["pass_dir"] = str(args.pass_dir or "")
    return emit_exit(payload)


if __name__ == "__main__":
    raise SystemExit(main())
