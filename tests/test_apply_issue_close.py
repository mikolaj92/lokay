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


def _live_apply(monkeypatch, *, repo, issue, decision, issue_data):
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
        repo=repo,
        issue=issue,
        decision=decision,
        live=True,
        issue_data=issue_data,
    )
    return out, comments, closes


def test_4995_reopen_with_proof_stays_open(monkeypatch) -> None:
    """Temida#4995: human reopened with proof; no merged PR named this issue."""
    issue_data = {
        "state": "OPEN",
        "number": 4995,
        "reopened": True,
        "proof": "Docxtor#29 merged; Posejdon still needs the pin",
        "merged_prs_naming_this_issue": [],
        "timeline": [
            {"event": "closed", "actor": "mikolaj92", "reason": "obsolete_argus_flow_assumption"},
            {"event": "reopened", "actor": "PSyron", "proof": True},
        ],
    }
    out, comments, closes = _live_apply(
        monkeypatch,
        repo="mikolaj92/temida",
        issue=4995,
        decision={"verdict": "close", "reason": "obsolete_argus_flow_assumption"},
        issue_data=issue_data,
    )
    assert out["refused"] is True
    assert out["applied"] is False
    assert comments == []
    assert closes == []


def test_205_guessed_linked_pr_merged_stays_open(monkeypatch) -> None:
    """reviewkit#205: agent guessed linked_pr_merged; timeline has no merged PR."""
    issue_data = {
        "state": "OPEN",
        "number": 205,
        "merged_prs_naming_this_issue": [],
        "timeline": [],
    }
    out, comments, closes = _live_apply(
        monkeypatch,
        repo="mikolaj92/reviewkit",
        issue=205,
        decision={"verdict": "close", "reason": "linked_pr_merged"},
        issue_data=issue_data,
    )
    assert out["refused"] is True
    assert out["applied"] is False
    assert comments == []
    assert closes == []


def test_human_reopen_never_closes_again_in_same_pass(monkeypatch) -> None:
    """After a human reopen, a second close in the same pass must refuse."""
    issue_data = {
        "state": "OPEN",
        "number": 4995,
        "reopened": True,
        "merged_prs_naming_this_issue": [],
    }
    first, comments_a, closes_a = _live_apply(
        monkeypatch,
        repo="mikolaj92/temida",
        issue=4995,
        decision={"verdict": "close", "reason": "obsolete_argus_flow_assumption"},
        issue_data=issue_data,
    )
    second, comments_b, closes_b = _live_apply(
        monkeypatch,
        repo="mikolaj92/temida",
        issue=4995,
        decision={"verdict": "close", "reason": "obsolete_argus_flow_assumption"},
        issue_data=issue_data,
    )
    assert first["refused"] is True and second["refused"] is True
    assert first["applied"] is False and second["applied"] is False
    assert comments_a == comments_b == []
    assert closes_a == closes_b == []
