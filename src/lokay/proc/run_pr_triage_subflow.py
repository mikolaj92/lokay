"""NODE slot: launch child Fala `pr_triage`. Do not implement that subgraph here."""

from lokay.graph_run import run_path

# Named slot for the PR sieve only. The parent `prs` graph consumes its
# verdict and may invoke the separate `pr_repair` department afterwards.
CHILD_PATH = "pr_triage"


def run(target: dict, *, config_path: str | None, live: bool) -> dict:
    result = run_path(
        path_id=CHILD_PATH,
        repo=str(target["repo"]),
        pr=int(target["pr"]),
        branch=str(target["branch"]),
        config_path=config_path,
        live=live,
    )
    result = dict(result)
    published = dict(result.get("publish_pr_review") or {})
    published_reason = str(published.get("reason") or "")
    terminal = result.get("terminal")
    summary = terminal.get("summarize_pr_triage") if isinstance(terminal, dict) else None
    if not isinstance(summary, dict):
        summary = terminal.get("summarize_pr_triage_department") if isinstance(terminal, dict) else None
    if not isinstance(summary, dict):
        summary = result.get("summarize_pr_triage")
    if isinstance(summary, dict):
        result = {**result, **summary}
        if isinstance(summary.get("result"), dict):
            result = {**result, **summary["result"]}
    raw_review = result.get("review")
    review = raw_review if isinstance(raw_review, dict) else {}
    check = dict(result.get("pr_checks") or {})
    check_route = dict(result.get("classify_pr_triage_checks") or {})
    review_decision = dict((result.get("publish_pr_review") or {}).get("decision") or {})
    repair_verdict = dict(result.get("pr_repair_verdict") or {})
    triage_outcome = dict(result.get("select_pr_triage_outcome") or {})
    head_sha = str(
        result.get("head_sha") or repair_verdict.get("head_sha")
        or triage_outcome.get("head_sha") or check_route.get("head_sha")
        or check.get("head_sha") or ""
    )
    repair_kind = str(
        result.get("repair_kind") or repair_verdict.get("repair_kind")
        or triage_outcome.get("repair_kind") or ""
    )
    # Later envelopes own even empty fields; review is only a legacy fallback.
    handoff = {**review, **triage_outcome, **repair_verdict, **result}
    return {
        "ok": True,
        **target,
        "route": "completed",
        "triage": {
            "repairable": bool(
                result.get("repairable")
                or (result.get("pr_repair_verdict") or {}).get("repairable")
                or (result.get("select_pr_triage_outcome") or {}).get("repairable")
            ),
            "reason": (
                published_reason
                or result.get("reason")
                or (result.get("pr_repair_verdict") or {}).get("reason")
                or (result.get("select_pr_triage_outcome") or {}).get("reason")
            ),
            "repair_kind": repair_kind,
            "head_sha": head_sha,
            "review": review or review_decision,
            "task": dict(handoff.get("task") or {}),
            "findings": list(handoff.get("findings") or []),
            "reviewed_head_sha": str(handoff.get("reviewed_head_sha") or ""),
            "task_identity_sha256": str(handoff.get("task_identity_sha256") or ""),
            "review_result_sha256": str(handoff.get("review_result_sha256") or ""),
            "repair_push_intent_sha256": str(result.get("repair_push_intent_sha256") or ""),
            "repair_start_head_sha": str(
                result.get("repair_start_head_sha") or repair_verdict.get("repair_start_head_sha")
                or triage_outcome.get("repair_start_head_sha") or review_decision.get("reviewed_head_sha") or ""
            ),
            "merged": bool(result.get("merged")),
            "waiting": bool(result.get("waiting")),
        },
    }
