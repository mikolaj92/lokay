"""Invoke the authored PR-repair Fala subflow for one reviewed PR head."""

from __future__ import annotations

import argparse
import json
from typing import Any

from lokay.compose.pr_repair import compose_pr_repair
from lokay.envelope import emit_exit, err
from lokay.proc._common import add_config_live


def run_pr_repair_subflow(
    *, config_path: str | None, repo: str, pr: int, branch: str,
    review: dict[str, Any], live: bool,
) -> dict[str, Any]:
    return compose_pr_repair(
        config_path=config_path, repo=repo, pr_number=pr, branch=branch,
        review=review, live=live,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-pr-repair-subflow")
    add_config_live(parser)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr", required=True, type=int)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--review-json", required=True)
    args = parser.parse_args(argv)
    try:
        review = json.loads(args.review_json)
    except json.JSONDecodeError as exc:
        return emit_exit(err(f"invalid review JSON: {exc}"))
    if not isinstance(review, dict):
        return emit_exit(err("review JSON object required"))
    return emit_exit(run_pr_repair_subflow(
        config_path=args.config, repo=args.repo, pr=args.pr, branch=args.branch,
        review=review, live=bool(args.live),
    ))


if __name__ == "__main__":
    raise SystemExit(main())
