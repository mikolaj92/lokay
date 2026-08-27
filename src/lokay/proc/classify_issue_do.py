"""Read whether sito said implement. One known triage envelope."""

from lokay.proc.walk_issue_leftover import CONSUME


def classify(triage_run: dict) -> dict:
    if triage_run.get("route") != "completed":
        text = str(triage_run.get("error") or triage_run.get("reason") or "")
        reason = (
            "adapter_failed"
            if "adapter_failed" in text or "adapter fail" in text.lower()
            else "triage_not_done"
        )
        return {
            "ok": True,
            "route": "not_ready",
            "implementable": False,
            "reason": reason,
        }
    blob = triage_run.get("triage")
    if not isinstance(blob, dict):
        blob = {}
    result = blob.get("result") if isinstance(blob.get("result"), dict) else {}
    decision = blob.get("decision") if isinstance(blob.get("decision"), dict) else {}
    if not decision:
        nested = result.get("decision")
        decision = nested if isinstance(nested, dict) else {}
    implementable = (
        blob.get("implementable") is True
        or result.get("implementable") is True
        or str(decision.get("verdict") or "") == "ready"
    )
    if implementable:
        return {
            "ok": True,
            "route": "ready",
            "implementable": True,
            "reason": None,
        }
    verdict = str(decision.get("verdict") or "")
    nested_reason = str(decision.get("reason") or result.get("reason") or "")
    reason = (
        verdict
        if verdict in CONSUME
        else nested_reason
        if nested_reason in CONSUME
        else "sito_nie_robic"
    )
    return {
        "ok": True,
        "route": "not_ready",
        "implementable": False,
        "reason": reason,
    }
