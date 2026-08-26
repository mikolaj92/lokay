"""Contracts for minimal detached-worker budget processes."""

import json
from pathlib import Path


def test_under_budget_routes_keep(monkeypatch):
    from lokay.proc.check_receipt_budget import check

    monkeypatch.setattr(
        "lokay.proc.check_receipt_budget.check_pi_budget",
        lambda pid, budget: {"over_budget": False, "elapsed_s": 12},
    )
    out = check({"pid": 7}, {"closed": False}, budget_s=480)
    assert out["route"] == "keep" and out["elapsed_s"] == 12


def test_closed_issue_routes_reap_even_under_budget(monkeypatch):
    from lokay.proc.check_receipt_budget import check

    monkeypatch.setattr(
        "lokay.proc.check_receipt_budget.check_pi_budget",
        lambda pid, budget: {"over_budget": False, "elapsed_s": 12},
    )
    out = check({"pid": 7}, {"closed": True}, budget_s=480)
    assert out["route"] == "reap" and out["closed"] is True


def test_unknown_coder_diff_keeps_fail_closed(monkeypatch):
    from lokay.proc.inspect_budget_coder_diff import inspect

    monkeypatch.setattr(
        "lokay.proc.inspect_budget_coder_diff.coder_diff",
        lambda pid: {"kind": "unknown", "worktree": ""},
    )
    assert inspect({"pid": 7})["route"] == "keep"


def test_plan_only_diff_routes_reap(monkeypatch, tmp_path):
    from lokay.proc.inspect_budget_coder_diff import inspect

    monkeypatch.setattr(
        "lokay.proc.inspect_budget_coder_diff.coder_diff",
        lambda pid: {"kind": "plan_only", "worktree": str(tmp_path)},
    )
    monkeypatch.setattr(
        "lokay.proc.inspect_budget_coder_diff.worktree_branch",
        lambda path: "ai/fix/9-x",
    )
    assert inspect({"pid": 7})["route"] == "reap"


def test_real_diff_routes_harvest_with_branch(monkeypatch, tmp_path):
    from lokay.proc.inspect_budget_coder_diff import inspect

    monkeypatch.setattr(
        "lokay.proc.inspect_budget_coder_diff.coder_diff",
        lambda pid: {"kind": "real", "worktree": str(tmp_path)},
    )
    monkeypatch.setattr(
        "lokay.proc.inspect_budget_coder_diff.worktree_branch",
        lambda path: "ai/fix/9-real",
    )
    out = inspect({"pid": 7})
    assert out["route"] == "harvest" and out["branch"] == "ai/fix/9-real"


def test_harvest_outcome_is_authoritative():
    from lokay.proc.select_budget_harvest_outcome import select

    route = {"ok": True, "route": "harvest"}
    created = {"ok": True, "route": "harvested", "pr": 77}
    assert select(route, {}, {}, created)["pr"] == 77


def test_stamped_closed_issue_does_not_park():
    from lokay.proc.reduce_over_budget_reap import reduce_state

    out = reduce_state(
        rows=[
            {
                "route": "reaped",
                "repo": "a/one",
                "issue": 9,
                "pid": 7,
                "reason": "issue_closed",
                "killed": True,
            }
        ],
        budget_s=480,
    )
    assert out["reaped_count"] == 1 and "park" not in out["reaped"][0]


def test_plan_only_park_is_reported():
    from lokay.proc.reduce_over_budget_reap import reduce_state

    park = {"ok": True, "removed": True}
    out = reduce_state(
        rows=[
            {
                "route": "reaped",
                "repo": "a/one",
                "issue": 9,
                "pid": 7,
                "reason": "over_budget",
                "killed": True,
                "park": park,
            }
        ],
        budget_s=480,
    )
    assert out["reaped"][0]["park"] == park


def test_catalog_empty_receipts_skip_physical_effects(monkeypatch):
    from lokay.proc.over_budget_catalog import run

    called = []

    def fail(*_a, **_k):
        called.append(True)
        raise AssertionError("physical effect must not run")

    monkeypatch.setattr("lokay.proc.inspect_budget_issue_state.inspect", fail)
    monkeypatch.setattr("lokay.proc.terminate_over_budget_worker.terminate", fail)
    monkeypatch.setattr("lokay.proc.commit_over_budget_diff.commit", fail)
    out = run(
        {"ok": True, "receipts": [], "stuck_path": "/tmp/stuck.json"},
        config_path=None,
        live=True,
        budget_s=480,
    )
    assert out["reaped_count"] == 0 and out["kept"] == [] and not called


def test_reap_over_budget_subflow_uses_handful_of_ticks():
    from lokay.proc.reap_over_budget_subflow import run
    import inspect

    source = inspect.getsource(run)
    assert "max_ticks=16" in source


def test_prepare_overflow_is_fail_closed(monkeypatch):
    from lokay.proc.prepare_over_budget_reap import prepare

    monkeypatch.setattr(
        "lokay.proc.prepare_over_budget_reap.live_issue_to_pr_receipts",
        lambda: [{}] * 31,
    )
    out = prepare(pass_dir=None, budget_s=480, slot_count=30)
    assert out["ok"] is False and "exceed authored slots" in out["error"]


def test_stamp_keeps_dead_receipt_for_harvest(tmp_path, monkeypatch):
    from lokay.proc.stamp_reaped_receipt import stamp

    path = tmp_path / "receipt.json"
    monkeypatch.setattr(
        "lokay.proc.stamp_reaped_receipt.issue_to_pr_receipt_path",
        lambda repo, issue: path,
    )
    out = stamp(
        {"repo": "a/one", "issue": 9, "receipt": {"pid": 7}, "reason": "over_budget"}
    )
    assert out["receipt_stamped"] and json.loads(path.read_text())["reaped"] is True
