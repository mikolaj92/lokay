"""After sito: ready means code and PR, anything else is next-pass."""


def _implementable(blob: object) -> bool:
    if not isinstance(blob, dict):
        return False
    if blob.get("implementable") is True:
        return True
    if str(blob.get("verdict") or "") == "ready":
        return True
    decision = blob.get("decision")
    if isinstance(decision, dict) and str(decision.get("verdict") or "") == "ready":
        return True
    result = blob.get("result")
    if isinstance(result, dict) and _implementable(result):
        return True
    triage = blob.get("triage")
    if isinstance(triage, dict) and _implementable(triage):
        return True
    return False


def select(picked: dict, triage_run: dict) -> dict:
    if picked.get("route") != "issue":
        return {"ok": True, "route": "skip", "reason": "no_issue"}
    if triage_run.get("route") != "completed":
        return {"ok": True, "route": "skip", "reason": "triage_not_done", **picked}
    if _implementable(triage_run):
        return {"ok": True, "route": "do", "repo": picked["repo"], "issue": picked["issue"]}
    return {"ok": True, "route": "skip", "reason": "sito_nie_robic", **picked}
