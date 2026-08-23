"""Invoke the authored bounded issue-split Fala subflow."""

from __future__ import annotations
import argparse
from lokay.envelope import emit_exit
from lokay.graph_run import run_path
from lokay.proc._common import add_config_live


def run(
    *, config_path: str | None, repo: str, issue: int, reason: str, live: bool
) -> dict:
    return run_path(
        path_id="issue_split",
        repo=repo,
        issue=issue,
        config_path=config_path,
        live=live,
        extra_inputs={"split_reason": reason or "agent_split"},
    )


def main(argv=None):
    parser = argparse.ArgumentParser(prog="lokay-issue-split")
    add_config_live(parser)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--issue", required=True, type=int)
    parser.add_argument("--reason", default="agent_split")
    args = parser.parse_args(argv)
    return emit_exit(
        run(
            config_path=args.config,
            repo=args.repo,
            issue=args.issue,
            reason=args.reason,
            live=bool(args.live),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
