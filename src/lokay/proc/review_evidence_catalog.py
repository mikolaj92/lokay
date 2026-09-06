"""Collect + verify one supplemental PR-review evidence kind in a single atom.

Collapses the four when-gated collect_review_* effectors and verify_review_evidence_sha
into one catalog (no Fala unroll). Collect procs stay callable; this atom dispatches.
"""

from __future__ import annotations

from lokay.envelope import ok

_COLLECTORS = {
    "pr_metadata": "lokay.proc.collect_review_pr_metadata",
    "changed_files": "lokay.proc.collect_review_changed_files",
    "diff_tail": "lokay.proc.collect_review_diff_tail",
    "commit_summary": "lokay.proc.collect_review_commit_summary",
}


def run(
    selected: dict,
    *,
    repo: str,
    pr: int,
    live: bool,
    expected_sha: str,
) -> dict:
    """Dispatch collect_* by evidence_kind, then SHA-verify; never needs_human."""
    if not selected.get("ok", True):
        return dict(selected)
    route = str(selected.get("route") or "")
    kind = str(selected.get("evidence_kind") or "").strip()
    if route != "evidence" or kind in {"", "none"}:
        return ok(route="not_applicable", evidence_kind=kind or "none")
    module_name = _COLLECTORS.get(kind)
    if module_name is None:
        return ok(
            route="fail_closed",
            reason="requested_review_evidence_unavailable",
            evidence_kind=kind,
        )
    module = __import__(module_name, fromlist=["collect"])
    collected = module.collect(repo=repo, pr=pr, live=live)
    if (
        not collected.get("ok", True)
        or collected.get("collected") is False
        or collected.get("probe_failed")
        or collected.get("additional_evidence") is None
    ):
        return ok(
            route="fail_closed",
            reason=str(
                collected.get("reason") or "requested_review_evidence_unavailable"
            ),
            evidence_kind=kind,
            probe_failed=bool(collected.get("probe_failed")),
        )
    from lokay.proc.verify_review_evidence_sha import verify

    result = verify(
        repo=repo, pr=pr, expected_sha=str(expected_sha or ""), live=live
    )
    if result.get("route") == "agent":
        result["additional_evidence"] = {
            "kind": kind,
            "value": collected["additional_evidence"],
        }
        result["evidence_kind"] = kind
    return result
