"""Nested and flat sieve decision handoff (#1105 continuation)."""

from lokay.sieve_decision import attach, collect, decision_of


def _d(issue, route="skip", reason="host_ops", repo="o/r"):
    return {"repo": repo, "issue": issue, "route": route, "reason": reason}


def test_attach_reads_flat_decisions():
    listed = {"ok": True, "issues": [{"repo": "o/r", "issue": 1, "labels": []}]}
    out = attach(listed, {"decisions": [_d(1)]})
    assert out["issues"][0]["sieve_decision"] == _d(1)


def test_attach_reads_decisions_nested_under_result():
    # The department nest lifts the sieve receipt under ``result``; the handoff
    # must find decisions in both shapes or the queue stalls on row one.
    listed = {"ok": True, "issues": [{"repo": "o/r", "issue": 1, "labels": []}]}
    triage = {"ok": True, "department": "issue_triage", "result": {"decisions": [_d(1)]}}
    out = attach(listed, triage)
    assert out["issues"][0]["sieve_decision"] == _d(1)


def test_attach_prefers_latest_decision_for_identity():
    listed = {"ok": True, "issues": [{"repo": "o/r", "issue": 1, "labels": []}]}
    triage = {"result": {"decisions": [_d(1, reason="old")]},
              "decisions": [_d(1, route="do", reason="ready")]}
    out = attach(listed, triage)
    assert out["issues"][0]["sieve_decision"]["reason"] == "ready"


def test_attach_keeps_rows_without_decision_and_drops_unbound():
    listed = {"ok": True, "issues": [{"repo": "o/r", "issue": 2, "labels": []}]}
    out = attach(listed, {"decisions": [_d(9)]})
    assert "sieve_decision" not in out["issues"][0]
    assert [r["issue"] for r in out["issues"]] == [2]


def test_envelope_reads_fala_flat_payload():
    from lokay.sieve_decision import envelope

    flat = {
        "ok": True,
        "department": "issue_triage",
        "decisions": [_d(42, reason="host_ops")],
        "leftover": 108,
        "leftover_issues": [{"repo": "o/r", "issue": 53}],
    }
    out = envelope(flat)
    assert out["decisions"] == [_d(42, reason="host_ops")]
    assert out["leftover_issues"][0]["issue"] == 53


def test_envelope_reads_nested_result():
    from lokay.sieve_decision import envelope

    nested = {"ok": True, "result": {"decisions": [_d(2, route="do", reason="ready")]}}
    assert envelope(nested)["decisions"] == [_d(2, route="do", reason="ready")]
