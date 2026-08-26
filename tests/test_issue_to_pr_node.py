"""Authored issue_to_pr NODE: leaves + issue_to_pr_delivery child; receipt always."""

import tomllib

from lokay.graph_run import find_default_package


def _raw() -> dict:
    pkg = tomllib.loads(find_default_package().read_text(encoding="utf-8"))
    return next(p for p in pkg["correlation_paths"] if p["id"] == "issue_to_pr")


def _lookup(envelope: dict, path: str) -> str:
    cur: object = envelope
    for part in path.split("."):
        if not isinstance(cur, dict):
            return ""
        cur = cur.get(part)
    return str(cur or "")


def simulate_issue_to_pr(facts: dict[str, dict]) -> dict[str, str]:
    """Apply authored conduction + when. Skipped upstream satisfies conduction."""
    status: dict[str, str] = {}

    def matches(when: dict) -> bool:
        if not when:
            return True
        upstream = str(when.get("upstream") or "")
        if status.get(upstream) != "succeeded":
            return False
        return _lookup(facts.get(upstream) or {}, str(when.get("path") or "")) == str(
            when.get("equals") or ""
        )

    pending = list(_raw()["effectors"])
    progressed = True
    while pending and progressed:
        progressed = False
        leftover = []
        for node in pending:
            deps = list(node.get("conduction") or [])
            if any(status.get(dep) not in {"succeeded", "skipped"} for dep in deps):
                leftover.append(node)
                continue
            name = str(node["id"])
            status[name] = "succeeded" if matches(dict(node.get("when") or {})) else "skipped"
            progressed = True
        pending = leftover
    assert not pending, [node["id"] for node in pending]
    return status


def test_closed_or_resumed_skips_delivery_and_still_receipts():
    status = simulate_issue_to_pr(
        {"resolve_existing_delivery": {"route": "no_effect", "reason": "issue_closed"}}
    )
    assert status["collect_existing_delivery_pr"] == "succeeded"
    assert status["collect_resumed_source"] == "succeeded"
    assert status["issue_to_pr_subflow"] == "skipped"
    assert status["close_existing_delivery"] == "skipped"
    assert status["issue_to_pr_no_effect"] == "succeeded"
    assert status["summarize_issue_to_pr"] == "succeeded"


def test_existing_pr_closeout_skips_delivery_then_receipt():
    status = simulate_issue_to_pr({"resolve_existing_delivery": {"route": "closeout"}})
    assert status["close_existing_delivery"] == "succeeded"
    assert status["issue_to_pr_subflow"] == "skipped"
    assert status["issue_to_pr_no_effect"] == "skipped"
    assert status["summarize_issue_to_pr"] == "succeeded"


def test_deliver_invokes_child_fala_then_receipt():
    status = simulate_issue_to_pr({"resolve_existing_delivery": {"route": "deliver"}})
    assert status["issue_to_pr_subflow"] == "succeeded"
    assert status["close_existing_delivery"] == "skipped"
    assert status["issue_to_pr_no_effect"] == "skipped"
    assert status["summarize_issue_to_pr"] == "succeeded"
