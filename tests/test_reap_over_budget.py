"""reap_over_budget: over-budget live i2pr is killed so occupy cannot last 40 min."""

from __future__ import annotations

import json
from pathlib import Path

from lokay.models import Issue
from lokay.proc import reap_over_budget
from lokay.proc.detach_issue_to_pr import issue_to_pr_receipt_path


def test_reaps_over_budget_live_receipt(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".lokay" / "cycle").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    path = issue_to_pr_receipt_path("a/one", 9)
    path.write_text(
        json.dumps({"ok": True, "pid": 4242, "repo": "a/one", "issue": 9}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        reap_over_budget,
        "live_issue_to_pr_receipts",
        lambda: [{"repo": "a/one", "issue": 9, "pid": 4242}],
    )
    monkeypatch.setattr(
        reap_over_budget,
        "check_pi_budget",
        lambda pid, budget: {
            "ok": True,
            "over_budget": True,
            "elapsed_s": 900,
            "budget_s": budget,
            "pid": pid,
        },
    )
    killed: list[int] = []
    monkeypatch.setattr(
        reap_over_budget,
        "terminate_issue_to_pr_pid",
        lambda pid: killed.append(pid) or True,
    )
    parked: list[list[str]] = []

    def fake_park(argv=None):
        parked.append(list(argv or []))
        return reap_over_budget.emit_exit(
            reap_over_budget.ok(applied=True, removed=True)
        )

    monkeypatch.setattr(reap_over_budget.p_park, "main", fake_park)
    out = reap_over_budget.run_reap_over_budget(budget_s=480)
    assert out["ok"] is True
    assert out["reaped_count"] == 1
    assert killed == [4242]
    assert path.exists()
    stamped = json.loads(path.read_text(encoding="utf-8"))
    assert stamped["ok"] is False
    assert stamped["reason"] == "over_budget"
    assert stamped["pid"] == 4242
    assert parked == [["--repo", "a/one", "--issue", "9"]]
    stuck = json.loads((home / ".lokay" / "stuck.json").read_text(encoding="utf-8"))
    row = stuck["issues"]["a/one#9"]
    assert row["blocked"] is True
    assert row["reason"] == "plan_only"
    assert row["last_error"] == "plan_only"


def test_keeps_under_budget_live_receipt(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".lokay" / "cycle").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    path = issue_to_pr_receipt_path("a/one", 9)
    path.write_text(
        json.dumps({"ok": True, "pid": 7, "repo": "a/one", "issue": 9}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        reap_over_budget,
        "live_issue_to_pr_receipts",
        lambda: [{"repo": "a/one", "issue": 9, "pid": 7}],
    )
    monkeypatch.setattr(
        reap_over_budget,
        "check_pi_budget",
        lambda pid, budget: {
            "ok": True,
            "over_budget": False,
            "elapsed_s": 12,
            "budget_s": budget,
            "pid": pid,
        },
    )
    monkeypatch.setattr(
        reap_over_budget,
        "terminate_issue_to_pr_pid",
        lambda pid: (_ for _ in ()).throw(AssertionError("must not kill")),
    )
    out = reap_over_budget.run_reap_over_budget(budget_s=480)
    assert out["ok"] is True
    assert out["reaped_count"] == 0
    assert out["kept"][0]["pid"] == 7
    assert path.exists()



def test_reaps_live_receipt_when_issue_is_closed(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".lokay" / "cycle").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    path = issue_to_pr_receipt_path("a/one", 9)
    path.write_text(
        json.dumps({"ok": True, "pid": 4242, "repo": "a/one", "issue": 9}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        reap_over_budget,
        "live_issue_to_pr_receipts",
        lambda: [{"repo": "a/one", "issue": 9, "pid": 4242}],
    )
    monkeypatch.setattr(
        reap_over_budget,
        "get_issue",
        lambda _runner, _config, repo, issue, live: Issue(
            repo=repo,
            number=issue,
            title="closed",
            body="",
            labels=[],
            assignees=[],
            url="",
            state="CLOSED",
        ),
    )
    monkeypatch.setattr(
        reap_over_budget,
        "check_pi_budget",
        lambda pid, budget: {
            "ok": True,
            "over_budget": False,
            "elapsed_s": 12,
            "budget_s": budget,
            "pid": pid,
        },
    )
    monkeypatch.setattr(
        reap_over_budget,
        "wrapper_has_coding_descendant",
        lambda _pid: (_ for _ in ()).throw(
            AssertionError("closed issue must reap despite live coder")
        ),
    )
    killed: list[int] = []
    monkeypatch.setattr(
        reap_over_budget,
        "terminate_issue_to_pr_pid",
        lambda pid: killed.append(pid) or True,
    )
    out = reap_over_budget.run_reap_over_budget(budget_s=480, live=True)
    assert out["ok"] is True
    assert out["reaped_count"] == 1
    assert killed == [4242]
    assert out["reaped"][0]["reason"] == "issue_closed"
    assert not out["reaped"][0].get("park")
    assert json.loads(path.read_text(encoding="utf-8"))["reason"] == "issue_closed"


def test_keeps_live_receipt_when_issue_is_open(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".lokay" / "cycle").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    path = issue_to_pr_receipt_path("a/one", 9)
    path.write_text(
        json.dumps({"ok": True, "pid": 4242, "repo": "a/one", "issue": 9}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        reap_over_budget,
        "live_issue_to_pr_receipts",
        lambda: [{"repo": "a/one", "issue": 9, "pid": 4242}],
    )
    monkeypatch.setattr(
        reap_over_budget,
        "get_issue",
        lambda _runner, _config, repo, issue, live: Issue(
            repo=repo,
            number=issue,
            title="open",
            body="",
            labels=[],
            assignees=[],
            url="",
            state="OPEN",
        ),
    )
    monkeypatch.setattr(
        reap_over_budget,
        "check_pi_budget",
        lambda pid, budget: {
            "ok": True,
            "over_budget": False,
            "elapsed_s": 12,
            "budget_s": budget,
            "pid": pid,
        },
    )
    monkeypatch.setattr(
        reap_over_budget,
        "terminate_issue_to_pr_pid",
        lambda _pid: (_ for _ in ()).throw(AssertionError("must not kill")),
    )
    out = reap_over_budget.run_reap_over_budget(budget_s=480, live=True)
    assert out["ok"] is True
    assert out["reaped_count"] == 0
    assert out["kept"] == [{"repo": "a/one", "issue": 9, "pid": 4242, "elapsed_s": 12.0}]
    assert path.exists()



def test_does_not_reap_wrapper_while_coder_lives(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".lokay" / "cycle").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    path = issue_to_pr_receipt_path("a/one", 9)
    path.write_text(
        json.dumps({"ok": True, "pid": 4242, "repo": "a/one", "issue": 9}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        reap_over_budget,
        "live_issue_to_pr_receipts",
        lambda: [{"repo": "a/one", "issue": 9, "pid": 4242}],
    )
    monkeypatch.setattr(
        reap_over_budget,
        "check_pi_budget",
        lambda pid, budget: {
            "ok": True,
            "over_budget": True,
            "elapsed_s": 900,
            "budget_s": budget,
            "pid": pid,
        },
    )
    monkeypatch.setattr(
        reap_over_budget,
        "wrapper_has_coding_descendant",
        lambda pid: True,
    )
    monkeypatch.setattr(
        reap_over_budget,
        "terminate_issue_to_pr_pid",
        lambda pid: (_ for _ in ()).throw(AssertionError("must not kill coder")),
    )
    out = reap_over_budget.run_reap_over_budget(budget_s=480)
    assert out["ok"] is True
    assert out["reaped_count"] == 0
    assert out["kept"][0]["reason"] == "coder_live"
    stamped = json.loads(path.read_text(encoding="utf-8"))
    assert stamped.get("reaped") is not True
