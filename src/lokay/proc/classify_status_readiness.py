"""Purely classify hard readiness blockers and policy notes."""


def classify(config: dict) -> dict:
    blockers = []
    if config.get("mode") != "live":
        blockers.append("mode is not live (need mode: live)")
    if not config.get("executor_enabled"):
        blockers.append("executor.enabled is false (agent never runs)")
    if not config.get("merge_enabled"):
        blockers.append("merge.enabled is false (PRs cannot merge)")
    notes = []
    if config.get("require_checks"):
        notes.append(
            "merge.require_checks=true: no-CI PRs wait (no_checks_blocked); green CI still merges"
        )
    if not config.get("require_llm_review"):
        notes.append(
            "merge.require_llm_review=false: merge without structured LLM review"
        )
    return {
        "ok": True,
        "lokay_ready": not blockers,
        "blockers": blockers,
        "policy_notes": notes,
    }
