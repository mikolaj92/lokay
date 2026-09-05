"""Atomic: gh pr checks classification. Read-only; network by default.

status: passed | failed | pending | none | offline
no_checks=true means the branch has no CI (not a failure).
"""

from __future__ import annotations

import argparse

from lokay.config import RepoConfig
from lokay.envelope import emit_exit, err, ok
from lokay.proc._common import add_config_read, load_cfg, read_live, runner
from lokay.source import load_code


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-pr-checks")
    add_config_read(p)
    p.add_argument("--repo", required=True)
    p.add_argument("--pr", required=True, type=int)
    args = p.parse_args(argv)
    live = read_live(args)
    cfg = load_cfg(args)
    repos = list(getattr(cfg, "repos", None) or [])
    repo = next((r for r in repos if getattr(r, "name", None) == args.repo), None)
    if repo is None:
        from pathlib import Path

        root = getattr(cfg, "worktrees_root", None)
        repo = RepoConfig(name=args.repo, clone_path=Path(root or "/tmp") / "unused")
    try:
        contract = load_code(repo, runner=runner(), config=cfg, live=live)
        checks = contract.pr.checks(args.pr)
        report = contract.pr.last_checks_report  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    status = str(checks.status or report.get("status") or "failed")
    green = status == "passed"
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
