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
    task: dict[str, Any] | None = None,
    findings: list[dict[str, Any]] | None = None,
    reviewed_head_sha: str = "",
    task_identity_sha256: str = "",
    review_result_sha256: str = "",
    repair_kind: str = "",
    repair_start_head_sha: str = "",
) -> dict[str, Any]:
    return compose_pr_repair(
        config_path=config_path, repo=repo, pr_number=pr, branch=branch,
        review=review, task=task, findings=findings,
        reviewed_head_sha=reviewed_head_sha,
        task_identity_sha256=task_identity_sha256,
        review_result_sha256=review_result_sha256,
        repair_kind=repair_kind, repair_start_head_sha=repair_start_head_sha, live=live,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-pr-repair-subflow")
    add_config_live(parser)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr", required=True, type=int)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--review-json", required=True)
    parser.add_argument("--task-json", default="")
    parser.add_argument("--findings-json", default="")
    parser.add_argument("--reviewed-head-sha", default="")
    parser.add_argument("--task-identity-sha256", default="")
    parser.add_argument("--review-result-sha256", default="")
    parser.add_argument("--repair-kind", choices=("ci", "review"), required=True)
    parser.add_argument("--repair-start-head-sha", default="")
    args = parser.parse_args(argv)
    try:
        review = json.loads(args.review_json)
        task = json.loads(args.task_json) if args.task_json else None
        findings = json.loads(args.findings_json) if args.findings_json else None
    except json.JSONDecodeError as exc:
        return emit_exit(err(f"invalid review JSON: {exc}"))
    if not isinstance(review, dict):
        return emit_exit(err("review JSON object required"))
    return emit_exit(run_pr_repair_subflow(
        config_path=args.config, repo=args.repo, pr=args.pr, branch=args.branch,
        review=review, task=task, findings=findings,
        reviewed_head_sha=args.reviewed_head_sha,
        task_identity_sha256=args.task_identity_sha256,
        review_result_sha256=args.review_result_sha256,
        repair_kind=args.repair_kind, repair_start_head_sha=args.repair_start_head_sha,
        live=bool(args.live),
    ))


if __name__ == "__main__":
    raise SystemExit(main())
