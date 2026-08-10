"""Fala-only composition for PR review/merge triage."""

from __future__ import annotations

import argparse

from lokay.config import load_config
from lokay.envelope import emit_exit
from lokay.graph_run import run_path
from lokay.proc._common import add_config_live
from lokay.state import append_event


def compose_pr_triage(
    *,
    config_path: str | None,
    repo: str,
    pr_number: int,
    branch: str,
    live: bool,
    keep_issue_open: bool = False,
    package_path: str | None = None,
) -> dict:
    if live and load_config(config_path).mode != "live":
        return {"ok": False, "error": "refusing live compose while config mode is not live"}
    if not branch:
        return {"ok": False, "error": "branch required for pr_triage"}

    result = run_path(
        path_id="pr_triage", repo=repo, pr=pr_number, branch=branch,
        config_path=config_path, live=live, package_path=package_path, extra_inputs={"keep_issue_open": keep_issue_open},
    )
    result.update(kind="pr_triage", engine="fala", planned=not live)
    try:
        append_event(load_config(config_path).state_path, result)
    except Exception:
        pass
    return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-pr-triage")
    add_config_live(p)
    p.add_argument("--repo", required=True)
    p.add_argument("--pr", required=True, type=int)
    p.add_argument("--branch", required=True)
    args = p.parse_args(argv)
    return emit_exit(compose_pr_triage(config_path=args.config, repo=args.repo, pr_number=args.pr, branch=args.branch, live=bool(args.live)))


if __name__ == "__main__":
    raise SystemExit(main())
