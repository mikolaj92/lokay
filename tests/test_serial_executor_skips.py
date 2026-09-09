"""Test sequence of 8 executor slots with all-skip sieve decisions."""

from lokay.proc.select_issue_do_row import select as select_do
from lokay.proc.select_next_issue import select as pick
from lokay.sieve_decision import decision_of


def test_serial_executor_slots_walk_past_all_skips():
    rows = [
        {"repo": "o/r", "issue": n, "labels": [], "sieve_decision": decision_of({"repo": "o/r", "issue": n, "route": "skip", "reason": "host_ops"})}
        for n in range(1, 9)
    ]
    listed = {"ok": True, "issues": rows}
    
    last = {}
    visited = []
    for slot in range(1, 9):
        picked = pick(listed, last, occupied=set())
        assert picked.get("issue") is not None, f"Slot {slot} got no issue"
        visited.append(picked["issue"])
        outcome = select_do(picked, listed)
        assert outcome["route"] == "skip"
        last = outcome

    assert visited == list(range(1, 9)), f"Expected 1..8, got {visited}"
