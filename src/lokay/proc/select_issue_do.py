"""Route do or skip. Two small functions: classify sito, then select."""

from lokay.proc.classify_issue_do import classify


def select(picked: dict, triage_run: dict) -> dict:
    repo = picked.get("repo")
    issue = picked.get("issue")
    if picked.get("route") != "issue":
        return {"ok": True, "route": "skip", "reason": "no_issue"}
    sito = classify(triage_run)
    if sito.get("route") != "ready":
        return {
            "ok": True,
            "repo": repo,
            "issue": issue,
            "route": "skip",
            "reason": sito.get("reason") or "sito_nie_robic",
        }
    return {"ok": True, "route": "do", "repo": repo, "issue": issue}
