"""Small issue-bound contract joining this pass's sieve to a fresh issue list."""

from typing import TypedDict


class SieveDecision(TypedDict):
    repo: str
    issue: int
    route: str
    reason: str | None


def decision_of(value: dict) -> SieveDecision | None:
    if (not isinstance(value, dict) or not isinstance(value.get("repo"), str)
            or type(value.get("issue")) is not int
            or not isinstance(value.get("route"), str)
            or value.get("route") not in {"do", "skip", "split"}
            or value.get("reason") in ("adapter_failed", "triage_not_done", "sito_nie_robic", "no_issue")):
        return None
    return {key: value.get(key) for key in ("repo", "issue", "route", "reason")}


def collect(*groups: list[dict]) -> list[SieveDecision]:
    """Keep one latest decision per identity, including a resumed cursor."""
    decisions = {}
    for group in groups:
        for value in group:
            decision = decision_of(value)
            if decision:
                decisions[(decision["repo"], decision["issue"])] = decision
    return list(decisions.values())


def envelope(triage: dict | None) -> dict:
    """Executor fuel from a sieve department receipt.

    Authored nests lift decisions under ``result``. Fala 0.9 flattens that
    nest onto the organ payload. Both shapes must hand off or the work queue
    restarts leftover at the last skipped ticket.
    """
    blob = dict(triage or {})
    inner = blob.get("result")
    if isinstance(inner, dict) and any(
        key in inner for key in ("decisions", "leftover", "leftover_issues", "listed")
    ):
        return inner
    return blob


def _decision_rows(triage: dict) -> list:
    """Decisions may sit flat or under the nest ``result`` (#1105 handoff)."""
    rows = list(triage.get("decisions") or [])
    inner = triage.get("result")
    if isinstance(inner, dict):
        rows = list(inner.get("decisions") or []) + rows
    return rows


def attach(listed: dict, triage: dict) -> dict:
    decisions = {}
    for raw in _decision_rows(triage):
        decision = decision_of(raw)
        if decision:
            decisions[(decision["repo"], decision["issue"])] = decision
    rows = []
    for raw in listed.get("issues") or []:
        row = dict(raw)
        row.pop("sieve_decision", None)
        decision = decisions.get((row.get("repo"), row.get("issue")))
        if decision:
            row["sieve_decision"] = decision
        rows.append(row)
    return {**listed, "issues": rows}


def listed_of(triage: dict | None, last: dict | None = None) -> dict:
    """One-pass issue snapshot for executor. Never a second GitHub list."""
    blob = envelope(triage)
    listed = blob.get("listed")
    if isinstance(listed, dict) and list(listed.get("issues") or []):
        return listed
    leftover = list(blob.get("leftover_issues") or [])
    if not leftover and isinstance(last, dict):
        leftover = [row for row in list(last.get("leftover_issues") or []) if isinstance(row, dict)]
    if leftover:
        return {
            "ok": True,
            "issues": leftover,
            "count": len(leftover),
            "overflow": False,
        }
    return listed if isinstance(listed, dict) else {}
