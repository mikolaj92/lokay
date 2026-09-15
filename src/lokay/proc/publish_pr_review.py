"""Publish one complete SHA-bound structured review in Lokay-owned policy."""

from __future__ import annotations

import argparse
import json
from typing import Any

from lokay.envelope import emit_exit, err, ok
from lokay.pr_review import PrReviewDecision, decide_review_merge, format_review_marker, labels_for_review
from lokay.pr_review_io import publish_fail_closed, publish_review
from lokay.proc.pr_review_artifacts import persist_result
from lokay.proc._common import add_config_live, load_cfg, mutations_allowed, runner


def _decision(value: dict[str, Any]) -> PrReviewDecision:
    verdict = str(value.get("verdict") or "fail_closed")
    if verdict not in {"approve", "request_changes", "needs_evidence", "fail_closed"}:
        verdict = "fail_closed"
    return PrReviewDecision(
        verdict=verdict,
        risk=str(value.get("risk") or "medium"),
        scope_ok=value.get("scope_ok") is True,
        secrets=value.get("secrets") is True,
        tests_adequate=value.get("tests_adequate") is True,
        blocking=tuple(str(item) for item in value.get("blocking") or []),
        summary=str(value.get("summary") or ""),
        findings=tuple(dict(item) for item in value.get("findings") or [] if isinstance(item, dict)),
        reviewed_head_sha=str(value.get("reviewed_head_sha") or ""),
        task=dict(value.get("task") or {}),
        task_identity_sha256=str(value.get("task_identity_sha256") or ""),
        review_result_sha256=str(value.get("review_result_sha256") or ""),
        review_input_fingerprint_sha256=str(value.get("review_input_fingerprint_sha256") or ""),
        review_preview_sha256=str(value.get("review_preview_sha256") or ""),
        review_rule_config_sha256=str(value.get("review_rule_config_sha256") or ""),
        review_runtime_config_sha256=str(value.get("review_runtime_config_sha256") or ""),
    )


def publish(*, cfg, repo: str, pr: int, evidence: dict, selected: dict, live: bool) -> dict:
    route = str(selected.get("route") or selected.get("selected_route") or "")
    if route in {"cached", "policy"}:
        decision = dict(selected.get("decision") or {})
        merge_ok = selected.get("merge_ok") is True
        count = int(selected.get("request_changes_count") or 0)
        return ok(
            repo=repo, pr=pr, head_sha=str(evidence.get("head_sha") or ""),
            decision=decision, merge_ok=merge_ok and not decision.get("findings"),
            escalated=(decision.get("verdict") == "request_changes"
                       and count >= max(1, int(getattr(cfg, "max_request_changes_per_pr", 2)))),
            request_changes_count=count, applied=False, execution={"source": route},
        )
    applied = mutations_allowed(live_flag=live, cfg=cfg)
    if route == "fail_closed":
        applied_fail_closed = publish_fail_closed(
            runner(cfg), repo, pr,
            ValueError(str(selected.get("reason") or "review_not_validated")),
            mutate=applied,
        )
        return ok(
            repo=repo, pr=pr, head_sha=str(evidence.get("head_sha") or ""),
            decision={"verdict": "fail_closed"}, merge_ok=False,
            reason=str(selected.get("reason") or "review_not_validated"),
            applied=applied_fail_closed, execution={"source": "open-code-review"},
        )
    if route != "publish":
        return ok(repo=repo, pr=pr, head_sha=str(evidence.get("head_sha") or ""),
                  decision={"verdict": "fail_closed"}, merge_ok=False,
                  reason=str(selected.get("reason") or "review_not_validated"),
                  applied=False, execution={"source": "open-code-review"})
    decision_data = selected.get("decision") if isinstance(selected.get("decision"), dict) else {}
    decision = _decision(decision_data)
    head = str(evidence.get("head_sha") or "")
    if not head or decision.reviewed_head_sha != head or decision.task_identity_sha256 != evidence.get("task_identity_sha256"):
        return err("selected review decision is not bound to current task and SHA", route="fail_closed")
    if decision.findings and decision.verdict != "request_changes":
        return err("findings cannot be published as approval", route="fail_closed")
    if not decision.findings and decision.verdict != "approve":
        return err("empty finding set must approve or fail closed", route="fail_closed")
    prior = int(selected.get("request_changes_count") or 0)
    merge_ok, escalated = decide_review_merge(
        decision, prior,
        max_request_changes=max(1, int(getattr(cfg, "max_request_changes_per_pr", 2))),
    )
    if not decision.review_result_sha256:
        return err("review result digest is required for durable publication", route="fail_closed")
    artifact = persist_result(
        cfg=cfg, repo=repo, pr=pr, evidence=evidence,
        decision=decision.to_dict(),
    )
    if not artifact.get("ok"):
        return err("durable review artifact could not be verified", route="fail_closed")
    marker = format_review_marker(
        head_sha=head, verdict=decision.verdict, merge_ok=merge_ok,
        result_sha256=decision.review_result_sha256,
        artifact_sha256=artifact["artifact_sha256"],
    )
    findings = [
        f"- `{item['path']}:{item['start_line']}-{item['end_line']}` ({item['severity']}, {item['category']}): {item['content']}"
        for item in decision.findings
    ]
    body = "\n".join([
        marker,
        f"## Lokay structured PR review: **{decision.verdict}**",
        "",
        decision.summary or "Review complete.",
        "",
        *( ["### Findings", *findings, ""] if findings else [] ),
        f"reviewed_head_sha={head}",
        f"task_identity_sha256={decision.task_identity_sha256}",
        f"review_result_sha256={decision.review_result_sha256}",
        f"review_artifact_sha256={artifact['artifact_sha256']}",
    ])
    if applied:
        publish_review(runner(cfg), repo, pr, body, labels_for_review(decision, escalated=escalated), live=True)
    return ok(
        repo=repo, pr=pr, head_sha=head,
        decision=decision.to_dict(), merge_ok=merge_ok and not decision.findings,
        escalated=escalated, applied=applied,
        request_changes_count=prior + (1 if decision.verdict == "request_changes" else 0),
        execution={"source": "open-code-review"},
    )


def main(argv=None):
    parser = argparse.ArgumentParser(prog="lokay-publish-pr-review")
    add_config_live(parser)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr", required=True, type=int)
    parser.add_argument("--evidence-json", required=True)
    parser.add_argument("--selected-json", required=True)
    args = parser.parse_args(argv)
    try:
        evidence, selected = json.loads(args.evidence_json), json.loads(args.selected_json)
    except json.JSONDecodeError as exc:
        return emit_exit(err(f"invalid publish input JSON: {exc}"))
    if not isinstance(evidence, dict) or not isinstance(selected, dict):
        return emit_exit(err("publish evidence and selection must be JSON objects"))
    return emit_exit(publish(cfg=load_cfg(args), repo=args.repo, pr=args.pr,
                             evidence=evidence, selected=selected, live=bool(args.live)))


if __name__ == "__main__":
    raise SystemExit(main())
