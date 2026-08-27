"""Route do or skip. Two small functions: classify sito, then leftover queue."""

from lokay.proc.classify_issue_do import classify
from lokay.proc.walk_issue_leftover import after


def leftover_of(picked: dict, listed: dict | None) -> tuple[int, list[dict]]:
    rows = list((listed or {}).get("issues") or [])
    if rows:
        leftover_rows = after(rows, picked)
        return len(leftover_rows), leftover_rows
    leftover_rows = list(picked.get("leftover_issues") or [])
    if leftover_rows:
        return len(leftover_rows), leftover_rows
    return int(picked.get("leftover") or 0), leftover_rows


def select(picked: dict, triage_run: dict, listed: dict | None = None) -> dict:
    leftover, leftover_issues = leftover_of(picked, listed)
    repo = picked.get("repo")
    issue = picked.get("issue")
    base = {
        "ok": True,
        "leftover": leftover,
        "leftover_issues": leftover_issues,
    }
    if picked.get("route") != "issue":
        return {**base, "route": "skip", "reason": "no_issue"}
    sito = classify(triage_run)
    if sito.get("route") != "ready":
        return {
            **base,
            "repo": repo,
            "issue": issue,
            "route": "skip",
            "reason": sito.get("reason") or "sito_nie_robic",
        }
    return {**base, "route": "do", "repo": repo, "issue": issue}
