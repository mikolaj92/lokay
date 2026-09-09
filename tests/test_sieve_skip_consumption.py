"""Test queue consumption on sieve skip decision (G2 & G3)."""

from lokay.proc.select_issue_do_row import select as select_do
from lokay.sieve_decision import decision_of


def test_bound_skip_decision_consumes_queue_item():
    # Sieve decision 'skip' with reason 'host_ops' must consume the item so
    # slot N+1 sees issue 2 instead of sticking to issue 1.
    rows = [
        {"repo": "o/r", "issue": 1, "labels": [], "sieve_decision": decision_of({"repo": "o/r", "issue": 1, "route": "skip", "reason": "host_ops"})},
        {"repo": "o/r", "issue": 2, "labels": [], "sieve_decision": decision_of({"repo": "o/r", "issue": 2, "route": "skip", "reason": "host_ops"})},
    ]
    listed = {"ok": True, "issues": rows}
    first = select_do({**rows[0], "route": "issue"}, listed)
    assert first["route"] == "skip"
    assert first["reason"] == "host_ops"
    assert [r["issue"] for r in first["leftover_issues"]] == [2]
