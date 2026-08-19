"""Merged closing PR closeout removes readiness before another issue-to-PR run."""

from __future__ import annotations

from types import SimpleNamespace

import lokay.compose.issue_to_pr as issue_to_pr
from lokay.proc import closeout


def test_open_issue_with_merged_fixes_pr_removes_ready_labels(monkeypatch):
    monkeypatch.setattr(
        closeout,
        "load_cfg",
        lambda _args: SimpleNamespace(config_path=None),
    )
    monkeypatch.setattr(closeout, "mutations_allowed", lambda **_kwargs: True)
    monkeypatch.setattr(
        closeout,
        "find_pr_fixing_issue",
        lambda _runner, _repo, _issue, live, merged_only: {
            "number": 41,
            "state": "closed",
            "merged_at": "2026-08-20T10:00:00Z",
            "body": "Fixes #7",
        },
    )
    parked: list[list[str]] = []

    def run_proc(_main, argv):
        parked.append(argv)
        return {"ok": True, "removed": True}

    monkeypatch.setattr(closeout, "run_proc", run_proc)

    out = closeout.run_closeout(
        repo="owner/repo", issue=7, config_path=None, live=True
    )

    assert out["delivered"] is True
    assert out["labels_removed"] is True
    assert parked == [["--repo", "owner/repo", "--issue", "7"]]


def test_existing_merged_delivery_is_closed_out_before_graph_can_start(monkeypatch):
    monkeypatch.delenv("LOKAY_ISSUE_TO_PR_ACTIVATION_FD", raising=False)
    monkeypatch.setattr(
        issue_to_pr, "load_config", lambda _path: SimpleNamespace(mode="live")
    )
    monkeypatch.setattr(
        issue_to_pr, "_delivery_stop_reason", lambda _repo, _issue: "delivery_pr_exists"
    )
    calls: list[list[str]] = []

    def run_proc(_main, argv):
        calls.append(argv)
        return {"ok": True, "delivered": True, "labels_removed": True}

    monkeypatch.setattr(issue_to_pr, "run_proc", run_proc)
    monkeypatch.setattr(
        issue_to_pr,
        "run_path",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("second i2pr must not start")),
    )

    out = issue_to_pr.compose_issue_to_pr(
        config_path=None, repo="owner/repo", issue_number=7, live=True
    )

    assert out["stopped"] is True
    assert out["closeout"]["labels_removed"] is True
    assert calls == [["--live", "--repo", "owner/repo", "--issue", "7"]]
