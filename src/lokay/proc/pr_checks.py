"""Atomic: gh pr checks classification. Read-only; network by default.

status: passed | failed | pending | none | offline
no_checks=true means the branch has no CI (not a failure).
"""

from __future__ import annotations

import argparse

from lokay.envelope import emit_exit, err, ok
from lokay.gh_prs import pr_checks_report
from lokay.proc._common import add_config_read, load_cfg, read_live, runner




def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-pr-checks")
    add_config_read(p)
    p.add_argument("--repo", required=True)
    p.add_argument("--pr", required=True, type=int)
    args = p.parse_args(argv)
    live = read_live(args)
    cfg = load_cfg(args)
    try:
        report = pr_checks_report(runner(), args.repo, args.pr, live=live)
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    status = str(report.get("status") or "failed")
    # Mergeable under strict CI policy only when passed.
    green = status == "passed"
    # Mergeable when no CI is required (repos without checks).
    merge_ok = green or (status == "none" and not cfg.require_checks)
    return emit_exit(
        ok(
            offline=not live,
            repo=args.repo,
            pr=args.pr,
            status=status,
            green=green,
            no_checks=bool(report.get("no_checks")),
            merge_ok=merge_ok,
            require_checks=cfg.require_checks,
            text=str(report.get("text") or "")[-4000:],
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
