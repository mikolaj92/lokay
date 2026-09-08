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


def attach(listed: dict, triage: dict) -> dict:
    decisions = {}
    for raw in triage.get("decisions") or []:
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
