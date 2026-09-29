"""Test mixed sieve decisions: unlabeled skip is not start fuel; sieve do is."""

from lokay.proc.select_issue_do_row import select as select_do
from lokay.proc.select_next_issue import select as pick
from lokay.sieve_decision import attach, decision_of


def test_mixed_decisions_sieve_to_executor_handoff():
    # 5 items evaluated by sieve: 4 skips, 1 do, remaining 3 not evaluated by sieve
    issues = [
        {"repo": "mikolaj92/msds-portal", "issue": 153, "labels": []},  # sieve: skip/host_ops
        {"repo": "mikolaj92/msds-portal", "issue": 155, "labels": []},  # sieve: skip/host_ops
        {"repo": "mikolaj92/msds-portal", "issue": 157, "labels": []},  # sieve: skip/host_ops
        {"repo": "mikolaj92/msds-portal", "issue": 159, "labels": []},  # sieve: skip/host_ops
        {"repo": "mikolaj92/Docxtor", "issue": 161, "labels": []},      # sieve: do/ready
        {"repo": "mikolaj92/Docxtor", "issue": 162, "labels": []},      # not in sieve (unlabeled)
        {"repo": "mikolaj92/Docxtor", "issue": 163, "labels": []},      # not in sieve (unlabeled)
    ]
    triage = {
        "decisions": [
            decision_of({"repo": "mikolaj92/msds-portal", "issue": 153, "route": "skip", "reason": "host_ops"}),
            decision_of({"repo": "mikolaj92/msds-portal", "issue": 155, "route": "skip", "reason": "host_ops"}),
            decision_of({"repo": "mikolaj92/msds-portal", "issue": 157, "route": "skip", "reason": "host_ops"}),
            decision_of({"repo": "mikolaj92/msds-portal", "issue": 159, "route": "skip", "reason": "host_ops"}),
            decision_of({"repo": "mikolaj92/Docxtor", "issue": 161, "route": "do", "reason": "ready"}),
        ]
    }
    listed = attach({"ok": True, "issues": issues}, triage)

    last = {}
    outcomes = []
    for slot in range(1, 8):
        picked = pick(listed, last, occupied=set())
        if picked.get("route") == "none":
            outcomes.append({"slot": slot, "route": "none", "reason": picked.get("reason")})
            break
        outcome = select_do(picked, listed)
        outcomes.append({"slot": slot, "issue": picked["issue"], "route": outcome["route"], "reason": outcome.get("reason")})
        last = outcome

    assert outcomes[0]["issue"] == 161
    assert outcomes[0]["route"] == "do"
    assert all(row.get("issue") not in {153, 155, 157, 159, 162, 163} for row in outcomes)
