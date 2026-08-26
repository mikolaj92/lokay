"""Read whether sito said implement. One known triage envelope."""


def classify(triage_run: dict) -> dict:
    if triage_run.get("route") != "completed":
        return {
            "ok": True,
            "route": "not_ready",
            "implementable": False,
            "reason": "triage_not_done",
        }
    blob = triage_run.get("triage")
    if not isinstance(blob, dict):
        blob = {}
    result = blob.get("result") if isinstance(blob.get("result"), dict) else {}
    decision = blob.get("decision") if isinstance(blob.get("decision"), dict) else {}
    implementable = (
        blob.get("implementable") is True
        or result.get("implementable") is True
        or str(decision.get("verdict") or "") == "ready"
    )
    return {
        "ok": True,
        "route": "ready" if implementable else "not_ready",
        "implementable": implementable,
        "reason": None if implementable else "sito_nie_robic",
    }
