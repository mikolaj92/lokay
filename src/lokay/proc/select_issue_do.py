"""Route do or skip. Two small functions: classify sito, then leftover queue."""

from lokay.proc.classify_issue_do import classify
from lokay.proc.walk_issue_leftover import after, consumes, identity, keep, row_is_ready


def leftover_of(
    picked: dict, listed: dict | None = None, *, consume: bool = False
) -> tuple[int, list[dict]]:
    rows = [
        dict(row)
        for row in list((listed or {}).get("issues") or [])
        if isinstance(row, dict)
    ]
    if rows:
        leftover_rows = (after if consume else keep)(rows, picked)
        return len(leftover_rows), leftover_rows
    leftover_rows = [
        dict(row)
        for row in list(picked.get("leftover_issues") or [])
        if isinstance(row, dict)
    ]
    if leftover_rows:
        seed: list[dict] = []
        if identity(picked) and identity(picked) != identity(leftover_rows[0]):
            seed.append(
                {
                    key: picked[key]
                    for key in ("repo", "issue", "title", "labels", "assignees")
                    if key in picked
                }
            )
        leftover_rows = (after if consume else keep)(seed + leftover_rows, picked)
        return len(leftover_rows), leftover_rows
    return int(picked.get("leftover") or 0), leftover_rows


def select(picked: dict, triage_run: dict, listed: dict | None = None) -> dict:
    sito = classify(triage_run)
    reason = sito.get("reason")
    consume = bool(sito.get("route") == "ready" or consumes(reason))
    leftover, leftover_issues = leftover_of(picked, listed, consume=consume)
    repo = picked.get("repo")
    issue = picked.get("issue")
    base = {
        "ok": True,
        "leftover": leftover,
        "leftover_issues": leftover_issues,
    }
    if picked.get("route") == "ready":
        leftover, leftover_issues = leftover_of(picked, listed, consume=False)
        return {
            **base,
            "leftover": leftover,
            "leftover_issues": leftover_issues,
            "route": "do",
            "repo": repo,
            "issue": issue,
        }
    if picked.get("route") != "issue":
        return {**base, "route": "skip", "reason": "no_issue"}
    if sito.get("route") == "ready":
        return {**base, "route": "do", "repo": repo, "issue": issue}
    if not consume and row_is_ready(picked):
        leftover, leftover_issues = leftover_of(picked, listed, consume=False)
        return {
            **base,
            "leftover": leftover,
            "leftover_issues": leftover_issues,
            "route": "do",
            "repo": repo,
            "issue": issue,
        }
    return {
        **base,
        "repo": repo,
        "issue": issue,
        "route": "skip",
        "reason": reason or "sito_nie_robic",
    }
