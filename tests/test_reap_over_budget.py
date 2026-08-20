"""reap_over_budget: over-budget live i2pr is killed so occupy cannot last 40 min."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lokay.models import Issue
from lokay.proc import reap_over_budget
from lokay.proc.detach_issue_to_pr import issue_to_pr_receipt_path


@pytest.mark.parametrize("repo", ["mikolaj92/Temida", "mikolaj92/takt"])
def test_skips_product_receipts_without_inspecting_or_mutating(repo, monkeypatch):
    receipt = {"repo": repo, "issue": 9, "pid": 4242}
    monkeypatch.setattr(
        reap_over_budget, "live_issue_to_pr_receipts", lambda: [receipt]
    )

    def unexpected(*_args, **_kwargs):
        raise AssertionError("product receipt must not be inspected or mutated")

    monkeypatch.setattr(reap_over_budget, "get_issue", unexpected)
    monkeypatch.setattr(reap_over_budget, "check_pi_budget", unexpected)
    monkeypatch.setattr(reap_over_budget, "terminate_issue_to_pr_pid", unexpected)
    monkeypatch.setattr(reap_over_budget, "issue_to_pr_receipt_path", unexpected)
    monkeypatch.setattr(reap_over_budget, "run_proc", unexpected)

    out = reap_over_budget.run_reap_over_budget(budget_s=480, live=True)

    assert out["ok"] is True
    assert out["skipped"] is True
    assert out["reason"] == "repo_not_delivered_by_mini_mill"
    assert out["reaped_count"] == 0
    assert out["reaped"] == []
    assert out["kept"] == []
    assert out["skipped_receipts"] == [
        {
            **receipt,
            "skipped": True,
            "reason": "repo_not_delivered_by_mini_mill",
        }
    ]


def test_reaps_over_budget_live_receipt(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".lokay" / "cycle").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    path = issue_to_pr_receipt_path("mikolaj92/lokay", 9)
    path.write_text(
        json.dumps({"ok": True, "pid": 4242, "repo": "mikolaj92/lokay", "issue": 9}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        reap_over_budget,
        "live_issue_to_pr_receipts",
        lambda: [{"repo": "mikolaj92/lokay", "issue": 9, "pid": 4242}],
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
    assert parked == [["--repo", "mikolaj92/lokay", "--issue", "9"]]
    stuck = json.loads((home / ".lokay" / "stuck.json").read_text(encoding="utf-8"))
    row = stuck["issues"]["mikolaj92/lokay#9"]
    assert row["blocked"] is True
    assert row["reason"] == "plan_only"
    assert row["last_error"] == "plan_only"


def test_keeps_under_budget_live_receipt(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".lokay" / "cycle").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    path = issue_to_pr_receipt_path("mikolaj92/lokay", 9)
    path.write_text(
        json.dumps({"ok": True, "pid": 7, "repo": "mikolaj92/lokay", "issue": 9}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        reap_over_budget,
        "live_issue_to_pr_receipts",
        lambda: [{"repo": "mikolaj92/lokay", "issue": 9, "pid": 7}],
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
    path = issue_to_pr_receipt_path("mikolaj92/lokay", 9)
    path.write_text(
        json.dumps({"ok": True, "pid": 4242, "repo": "mikolaj92/lokay", "issue": 9}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        reap_over_budget,
        "live_issue_to_pr_receipts",
        lambda: [{"repo": "mikolaj92/lokay", "issue": 9, "pid": 4242}],
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
    path = issue_to_pr_receipt_path("mikolaj92/lokay", 9)
    path.write_text(
        json.dumps({"ok": True, "pid": 4242, "repo": "mikolaj92/lokay", "issue": 9}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        reap_over_budget,
        "live_issue_to_pr_receipts",
        lambda: [{"repo": "mikolaj92/lokay", "issue": 9, "pid": 4242}],
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
    assert out["kept"] == [{"repo": "mikolaj92/lokay", "issue": 9, "pid": 4242, "elapsed_s": 12.0}]
    assert path.exists()



def test_harvests_over_budget_coder_with_real_diff(tmp_path, monkeypatch):
    home = tmp_path / "home"
    worktree = tmp_path / "wt"
    worktree.mkdir()
    (home / ".lokay" / "cycle").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    path = issue_to_pr_receipt_path("mikolaj92/lokay", 9)
    path.write_text(
        json.dumps({"ok": True, "pid": 4242, "repo": "mikolaj92/lokay", "issue": 9}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        reap_over_budget,
        "live_issue_to_pr_receipts",
        lambda: [{"repo": "mikolaj92/lokay", "issue": 9, "pid": 4242}],
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
        reap_over_budget, "wrapper_has_coding_descendant", lambda pid: True
    )
    monkeypatch.setattr(reap_over_budget, "_coder_has_real_diff", lambda pid: True)
    monkeypatch.setattr(reap_over_budget, "_coder_worktree", lambda pid: worktree)
    monkeypatch.setattr(reap_over_budget, "_worktree_branch", lambda wt: "ai/fix/9-real")
    monkeypatch.setattr(
        reap_over_budget,
        "terminate_issue_to_pr_pid",
        lambda pid: (_ for _ in ()).throw(AssertionError("must not kill coder")),
    )
    calls: list[tuple[str, list[str]]] = []

    def fake_run_proc(main, argv):
        name = getattr(main, "__module__", "")
        calls.append((name, list(argv)))
        if name.endswith("commit_all"):
            return {"ok": True, "committed": True, "commit": "abc"}
        if name.endswith("push_branch"):
            return {"ok": True}
        if name.endswith("pr_create"):
            return {"ok": True, "pr": 77, "head": "ai/fix/9-real"}
        raise AssertionError(main)

    monkeypatch.setattr(reap_over_budget, "run_proc", fake_run_proc)

    out = reap_over_budget.run_reap_over_budget(budget_s=1800, live=True)

    assert out["ok"] is True
    assert out["reaped_count"] == 0
    assert out["kept"][0]["reason"] == "harvested"
    assert out["kept"][0]["pr"] == 77
    assert any(name.endswith("commit_all") for name, _ in calls)
    assert any(name.endswith("push_branch") for name, _ in calls)
    assert any(name.endswith("pr_create") for name, _ in calls)
    stamped = json.loads(path.read_text(encoding="utf-8"))
    assert stamped.get("reaped") is not True


def test_does_not_reap_wrapper_while_coder_lives(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".lokay" / "cycle").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    path = issue_to_pr_receipt_path("mikolaj92/lokay", 9)
    path.write_text(
        json.dumps({"ok": True, "pid": 4242, "repo": "mikolaj92/lokay", "issue": 9}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        reap_over_budget,
        "live_issue_to_pr_receipts",
        lambda: [{"repo": "mikolaj92/lokay", "issue": 9, "pid": 4242}],
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
    monkeypatch.setattr(reap_over_budget, "_coder_has_real_diff", lambda pid: True)
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


def test_coder_diff_classification_uses_coder_worktree(tmp_path, monkeypatch):
    monkeypatch.setattr(
        reap_over_budget,
        "_child_pids",
        lambda pid: [200] if pid == 100 else [],
    )
    monkeypatch.setattr(
        reap_over_budget,
        "_pid_command",
        lambda pid: "pi implement GitHub issue #9" if pid == 200 else "wrapper",
    )
    monkeypatch.setattr(reap_over_budget, "_process_cwd", lambda pid: tmp_path)
    monkeypatch.setattr(
        reap_over_budget,
        "list_changed_paths",
        lambda run, worktree, base: [".lokay/approach.md"],
    )

    assert reap_over_budget._coder_has_real_diff(100) is False

    monkeypatch.setattr(
        reap_over_budget,
        "list_changed_paths",
        lambda run, worktree, base: ["src/product.py"],
    )
    assert reap_over_budget._coder_has_real_diff(100) is True


def test_reaps_coder_with_plan_only_diff(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".lokay" / "cycle").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    path = issue_to_pr_receipt_path("mikolaj92/lokay", 9)
    path.write_text(
        json.dumps({"ok": True, "pid": 4242, "repo": "mikolaj92/lokay", "issue": 9}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        reap_over_budget,
        "live_issue_to_pr_receipts",
        lambda: [{"repo": "mikolaj92/lokay", "issue": 9, "pid": 4242}],
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
        reap_over_budget, "wrapper_has_coding_descendant", lambda pid: True
    )
    monkeypatch.setattr(reap_over_budget, "_coder_has_real_diff", lambda pid: False)
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

    def fake_close(argv=None):
        raise AssertionError(f"plan_only must not close the issue: {argv}")

    monkeypatch.setattr("lokay.proc.close_issue.main", fake_close)

    out = reap_over_budget.run_reap_over_budget(budget_s=480)

    assert out["ok"] is True
    assert out["reaped_count"] == 1
    assert killed == [4242]
    assert parked == [["--repo", "mikolaj92/lokay", "--issue", "9"]]
    stamped = json.loads(path.read_text(encoding="utf-8"))
    assert stamped["reaped"] is True
    stuck = json.loads((home / ".lokay" / "stuck.json").read_text(encoding="utf-8"))
    assert stuck["issues"]["mikolaj92/lokay#9"]["reason"] == "plan_only"


def test_keeps_coder_when_diff_cannot_be_inspected(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".lokay" / "cycle").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(
        reap_over_budget,
        "live_issue_to_pr_receipts",
        lambda: [{"repo": "mikolaj92/lokay", "issue": 9, "pid": 4242}],
    )
    monkeypatch.setattr(
        reap_over_budget,
        "check_pi_budget",
        lambda pid, budget: {"over_budget": True, "elapsed_s": 900},
    )
    monkeypatch.setattr(
        reap_over_budget, "wrapper_has_coding_descendant", lambda pid: True
    )
    monkeypatch.setattr(reap_over_budget, "_coder_has_real_diff", lambda pid: None)
    monkeypatch.setattr(
        reap_over_budget,
        "terminate_issue_to_pr_pid",
        lambda pid: (_ for _ in ()).throw(AssertionError("must fail closed")),
    )

    out = reap_over_budget.run_reap_over_budget(budget_s=480)

    assert out["reaped_count"] == 0
    assert out["kept"][0]["reason"] == "coder_live"
