"""reap_over_budget: over-budget live i2pr is killed so occupy cannot last 40 min."""

from __future__ import annotations

import json
from pathlib import Path

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
    out = reap_over_budget.run_reap_over_budget(budget_s=480)
    assert out["ok"] is True
    assert out["reaped_count"] == 1
    assert killed == [4242]
    assert path.exists()
    stamped = json.loads(path.read_text(encoding="utf-8"))
    assert stamped["ok"] is False
    assert stamped["reason"] == "over_budget"
    assert stamped["pid"] == 4242


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
