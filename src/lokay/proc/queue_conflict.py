"""One job: contradiction gate over ready candidates before issue_to_pr.

Covering-PR matches stay deterministic. Semantic remainder is one structured
agent call. Queue hygiene — not a parallel scheduler.
"""

from __future__ import annotations

import argparse
from typing import Any

from lokay.envelope import emit_exit, err, ok, read_stdin_json
from lokay.models import Issue
from lokay.proc._common import add_config_live
from lokay.queue_conflict import READY
from lokay.queue_conflict_agent import evaluate_queue_conflict_with_agent


def evaluate_stdin(payload: dict[str, Any]) -> dict[str, Any]:
    """Single-candidate mode for tests / select enrichment."""
    raw = payload.get("issue") or payload.get("selected")
    if not isinstance(raw, dict):
        return err("stdin must include issue{} object")
    issue = Issue.from_dict(raw)
    verdict = evaluate_queue_conflict_with_agent(
        issue,
        runner=None,
        config=None,
        execute=False,
        open_prs=list(payload.get("open_prs") or []),
        peer_issues=list(payload.get("peer_issues") or []),
        branch_prefix=str(payload.get("branch_prefix") or "ai/fix/"),
        ready_label=str(payload.get("ready_label") or "ai:ready"),
        tracker_label=str(payload.get("tracker_label") or "ai:tracker"),
    )
    return ok(
        outcome=verdict.outcome,
        reason=verdict.reason,
        detail=verdict.detail,
        comment=verdict.comment,
        add_labels=verdict.add_labels,
        remove_labels=verdict.remove_labels,
        selected=issue.to_dict() if verdict.outcome == READY else None,
        verdict=verdict.to_dict(),
    )


def run_queue_conflict(
    *, pass_dir: str, config_path: str | None, live: bool
) -> dict[str, Any]:
    """Compatibility facade: product topology is the queue_conflict Fala."""
    from lokay.proc.queue_conflict_subflow import run

    return run(pass_dir=pass_dir, config_path=config_path, live=live)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-queue-conflict")
    add_config_live(parser)
    parser.add_argument(
        "--pass-dir",
        default="",
        help="factory pass workspace (filters ready_by_repo)",
    )
    args = parser.parse_args(argv)
    if args.pass_dir:
        return emit_exit(
            run_queue_conflict(
                pass_dir=str(args.pass_dir),
                config_path=args.config,
                live=bool(args.live),
            )
        )
    payload = read_stdin_json()
    if not isinstance(payload, dict):
        return emit_exit(err("stdin must be JSON object"))
    return emit_exit(evaluate_stdin(payload))


if __name__ == "__main__":
    raise SystemExit(main())
