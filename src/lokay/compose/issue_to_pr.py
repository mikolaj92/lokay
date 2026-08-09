"""Fala-only composition for issue → PR."""

from __future__ import annotations

import argparse

from lokay.config import load_config
from lokay.envelope import emit_exit
from lokay.graph_run import run_path
from lokay.proc._common import add_config_live
from lokay.state import append_event


def compose_issue_to_pr(
    *,
    config_path: str | None,
    repo: str,
    issue_number: int,
    live: bool,
) -> dict:
    if live and load_config(config_path).mode != "live":
        return {"ok": False, "error": "refusing live compose while config mode is not live"}

    result = run_path(
        path_id="issue_to_pr", repo=repo, issue=issue_number,
        config_path=config_path, live=live,
    )
    result.update(kind="issue_to_pr", engine="fala", planned=not live)
    try:
        append_event(load_config(config_path).state_path, result)
    except Exception:
        pass
    return result


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-issue-to-pr")
    add_config_live(p)
    p.add_argument("--repo", required=True)
    p.add_argument("--issue", required=True, type=int)
    args = p.parse_args(argv)
    return emit_exit(compose_issue_to_pr(config_path=args.config, repo=args.repo, issue_number=args.issue, live=bool(args.live)))


if __name__ == "__main__":
    raise SystemExit(main())
