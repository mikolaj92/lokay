"""apply_issue_close must not close a still-open product issue."""

from __future__ import annotations

from lokay.proc.apply_issue_close import apply


class _Runner:
    def __init__(self) -> None:
        self.calls: list[str] = []


def test_still_open_live_refuses_without_comment_or_close(monkeypatch) -> None:
    runner = _Runner()
    comments: list[tuple] = []
    closes: list[tuple] = []
    monkeypatch.setattr(
        "lokay.proc.apply_issue_close.comment_issue",
        lambda *a, **k: comments.append((a, k)),
    )
    monkeypatch.setattr(
        "lokay.proc.apply_issue_close.close_issue",
        lambda *a, **k: closes.append((a, k)),
    )
    out = apply(
        runner=runner,
        repo="mikolaj92/temida",
        issue=4995,
        decision={"verdict": "close", "reason": "obsolete_argus_flow_assumption"},
        live=True,
        issue_data={"state": "OPEN", "number": 4995},
    )
    assert out["ok"] is True
    assert out["planned"] is True
    assert out["refused"] is True
    assert out["applied"] is False
    assert out["reason"] == "still_open"
    assert comments == []
    assert closes == []


def test_already_closed_may_still_close(monkeypatch) -> None:
    comments: list[tuple] = []
    closes: list[tuple] = []
    monkeypatch.setattr(
        "lokay.proc.apply_issue_close.comment_issue",
        lambda *a, **k: comments.append((a, k)),
    )
    monkeypatch.setattr(
        "lokay.proc.apply_issue_close.close_issue",
        lambda *a, **k: closes.append((a, k)),
    )
    out = apply(
        runner=object(),
        repo="a/b",
        issue=1,
        decision={"verdict": "close", "reason": "issue_already_closed"},
        live=True,
        issue_data={"state": "CLOSED", "number": 1},
    )
    assert out["applied"] is True
    assert out["verdict"] == "close"
    assert len(comments) == 1
    assert len(closes) == 1


def test_missing_state_is_treated_as_open(monkeypatch) -> None:
    monkeypatch.setattr("lokay.proc.apply_issue_close.comment_issue", lambda *a, **k: None)
    monkeypatch.setattr("lokay.proc.apply_issue_close.close_issue", lambda *a, **k: None)
    out = apply(
        runner=object(),
        repo="a/b",
        issue=205,
        decision={"verdict": "close", "reason": "linked_pr_merged"},
        live=True,
    )
    assert out["refused"] is True
    assert out["applied"] is False
