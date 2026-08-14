"""One job: return abandoned ai:in-progress issues to ai:ready."""

from __future__ import annotations

import argparse
from typing import Any

from lokay.envelope import emit_exit, err, ok
from lokay.gh_issues import list_labeled_issues
from lokay.passkit import io as pass_io
from lokay.passkit.support import run_proc
from lokay.proc import stage_label as p_stage
from lokay.proc._common import add_config_live, load_cfg, runner
from lokay.proc.detach_issue_to_pr import live_issue_to_pr_receipts
from lokay.stage_ledger import LABEL_IMPLEMENTING
from lokay.stale_implementing import issue_has_covering_pr, should_reap_implementing


def _live_job_keys() -> set[tuple[str, int]]:
    out: set[tuple[str, int]] = set()
    for row in live_issue_to_pr_receipts():
        try:
            out.add((str(row["repo"]), int(row["issue"])))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def run_reap_stale_implementing(
    *, pass_dir: str | None, config_path: str | None, live: bool
) -> dict[str, Any]:
    cfg = load_cfg(argparse.Namespace(config=config_path))
    cfg_flag = ["--config", config_path] if config_path else []
    live_flag = ["--live"] if live else []
    live_jobs = _live_job_keys()
    prs_by_repo: dict[str, list] = {}
    if pass_dir:
        working = pass_io.read_json(pass_io.working_path(pass_dir))
        prs_by_repo = dict(working.get("prs_by_repo") or {})
    reaped: list[dict[str, Any]] = []
    kept: list[dict[str, Any]] = []
    prefix = str(cfg.branch_prefix or "ai/fix")
    for repo in cfg.active_repos():
        issues = list_labeled_issues(
            runner(cfg), cfg, repo, label=LABEL_IMPLEMENTING, live=live
        )
        prs = list(prs_by_repo.get(repo.name) or [])
        for issue in issues:
            num = int(issue.number)
            live_job = (repo.name, num) in live_jobs
            covering = issue_has_covering_pr(num, prs, branch_prefix=prefix)
            if not should_reap_implementing(
                has_live_job=live_job, has_covering_pr=covering
            ):
                kept.append({"repo": repo.name, "issue": num, "live_job": live_job})
                continue
            if live:
                staged = run_proc(
                    p_stage.main,
                    [*cfg_flag, *live_flag, "--repo", repo.name, "--issue", str(num), "--stage", "ready"],
                )
            else:
                staged = {"ok": True, "planned": True, "stage": "ready"}
            reaped.append({"repo": repo.name, "issue": num, **staged})
    return ok(
        planned=not live,
        reaped=reaped,
        kept=kept,
        reaped_count=len(reaped),
        pass_dir=pass_dir or "",
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-reap-stale-implementing")
    add_config_live(p)
    p.add_argument("--pass-dir", default="")
    args = p.parse_args(argv)
    try:
        payload = run_reap_stale_implementing(
            pass_dir=str(args.pass_dir or "") or None,
            config_path=args.config,
            live=bool(args.live),
        )
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    return emit_exit(payload)


if __name__ == "__main__":
    raise SystemExit(main())
