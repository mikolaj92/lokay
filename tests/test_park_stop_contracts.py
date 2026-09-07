"""Contract fixtures for park ≠ needs-feedback triage micro-nodes."""

from __future__ import annotations

from types import SimpleNamespace

from lokay.models import Issue
from lokay.proc.apply_issue_manual import apply as apply_manual
from lokay.proc.select_park_stop import MACHINE_PARK_LABEL, select as select_park_stop
from lokay.proc.select_triage_leaf import select as select_triage_leaf
from lokay.triage import decide_issue


def _issue(**kwargs) -> Issue:
    base = dict(
        repo="a/b",
        number=1,
        title="Implement useful feature with enough title chars",
        body="A sufficiently detailed body with clear acceptance criteria.\n",
        labels=[],
        assignees=["mikolaj92"],
        url="https://example.test/1",
        state="OPEN",
    )
    base.update(kwargs)
    return Issue(**base)


def test_select_triage_leaf_routes_known_verdicts():
    for verdict in ("ready", "skip", "blocked", "close", "park"):
        out = select_triage_leaf(final={"decision": {"verdict": verdict, "reason": "x"}})
        assert out == {
            "ok": True,
            "route": verdict,
            "reason": "x",
            "decision": {"verdict": verdict, "reason": "x"},
        }


def test_select_triage_leaf_fails_unknown_verdict():
    out = select_triage_leaf(final={"decision": {"verdict": "needs_feedback"}})
    assert out["ok"] is True
    assert out["route"] == "fail"
    assert out["reason"] == "unknown_triage_verdict"


def test_select_park_stop_machine_frozen_never_needs_feedback():
    cases = (
        {"verdict": "park", "reason": "invalid_triage_json_exhausted"},
        {"verdict": "park", "reason": "host_ops", "summary": "unpark when ops ready"},
        {"verdict": "park", "reason": "agent_park", "summary": "machine reason"},
        {"verdict": "park", "reason": "issue_evidence_exhausted"},
    )
    for decision in cases:
        out = select_park_stop(decision=decision)
        assert out["ok"] is True
        assert out["route"] == "park"
        assert out["labels"] == [MACHINE_PARK_LABEL]
        assert "ai:needs-feedback" not in out["labels"]
        assert out["reason"] == decision["reason"]


def test_select_park_stop_not_applicable_outside_park():
    out = select_park_stop(decision={"verdict": "ready", "reason": "ok"})
    assert out == {"ok": True, "route": "not_applicable", "reason": "not_park"}


def test_apply_manual_stamps_frozen_not_needs_feedback(monkeypatch):
    labeled: list[list[str]] = []
    comments: list[str] = []

    def _labels(runner, repo, issue, labels, *, live):
        labeled.append(list(labels))

    def _comment(runner, repo, issue, note, *, live):
        comments.append(note)

    monkeypatch.setattr("lokay.proc.apply_issue_manual.add_issue_labels", _labels)
    monkeypatch.setattr("lokay.proc.apply_issue_manual.comment_issue", _comment)
    cfg = SimpleNamespace(needs_feedback_label="ai:needs-feedback")
    stop = select_park_stop(
        decision={"verdict": "park", "reason": "invalid_triage_json_exhausted"}
    )
    out = apply_manual(
        runner=object(),
        cfg=cfg,
        repo="o/r",
        issue=7,
        decision={"verdict": "park", "reason": "invalid_triage_json_exhausted"},
        live=True,
        park_stop=stop,
    )
    assert out["ok"] is True
    assert out["labels"] == ["ai:frozen"]
    assert labeled == [["ai:frozen"]]
    assert "invalid_triage_json_exhausted" in comments[0]
    assert "ai:needs-feedback" not in "".join(comments)


def test_apply_manual_host_ops_frozen_with_structured_reason(monkeypatch):
    labeled: list[list[str]] = []
    comments: list[str] = []

    def _labels(runner, repo, issue, labels, *, live):
        labeled.append(list(labels))

    def _comment(runner, repo, issue, note, *, live):
        comments.append(note)

    monkeypatch.setattr("lokay.proc.apply_issue_manual.add_issue_labels", _labels)
    monkeypatch.setattr("lokay.proc.apply_issue_manual.comment_issue", _comment)
    cfg = SimpleNamespace(needs_feedback_label="ai:needs-feedback")
    decision = {
        "verdict": "park",
        "reason": "host_ops",
        "summary": "Unpark when host ops criterion met",
    }
    stop = select_park_stop(decision=decision)
    out = apply_manual(
        runner=object(),
        cfg=cfg,
        repo="o/r",
        issue=8,
        decision=decision,
        live=True,
        park_stop=stop,
    )
    assert out["labels"] == ["ai:frozen"]
    assert labeled == [["ai:frozen"]]
    assert "host_ops" in comments[0]
    assert "ai:needs-feedback" not in "".join(comments)


def test_apply_manual_refuses_when_park_stop_not_admitted():
    out = apply_manual(
        runner=object(),
        cfg=SimpleNamespace(needs_feedback_label="ai:needs-feedback"),
        repo="o/r",
        issue=1,
        decision={"verdict": "park", "reason": "x"},
        live=True,
        park_stop={"ok": True, "route": "fail"},
    )
    assert out["ok"] is False
    assert out["error"] == "park_stop_not_admitted"


def test_decide_issue_still_needs_feedback_for_short_title_body():
    short_title = decide_issue(_issue(title="fix"))
    assert short_title.decision == "needs_feedback"
    assert short_title.reason == "title_too_short"
    assert short_title.add_labels == ("ai:needs-feedback",)
    short_body = decide_issue(_issue(body="too short"))
    assert short_body.decision == "needs_feedback"
    assert short_body.reason == "body_too_short"
    assert short_body.add_labels == ("ai:needs-feedback",)
