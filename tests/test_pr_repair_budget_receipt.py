"""Per-PR pr_repair lifetime K via durable receipt (#1035)."""

from __future__ import annotations

from pathlib import Path

import pytest

from lokay.proc import pr_repair_receipts as receipts
from lokay.proc.run_parent_pr_repair_subflow import run as run_parent
from lokay.proc.run_pr_repair_department import run as run_department
from lokay.proc.select_pr_repair_department import select


def _repairable(**extra: object) -> dict:
    return {
        "triage": {
            "repairable": True,
            "reason": "red_ci",
            "review": {"verdict": "request_changes"},
        },
        "verdict": "repair",
        "repo": "o/r",
        "pr": 9,
        "branch": "ai/fix/9-x",
        **extra,
    }


def test_stamp_increments_and_parks(tmp_path: Path) -> None:
    first = receipts.stamp("o/r", 9, state_dir=tmp_path, budget=1, head_sha="abc", terminal="push")
    assert first["attempts"] == 1
    assert first["budget"] == 1
    assert first["parked"] is True
    assert first["last_head_sha"] == "abc"
    second = receipts.stamp("o/r", 9, state_dir=tmp_path, budget=1)
    assert second["attempts"] == 2
    assert second["parked"] is True
    loaded = receipts.read("o/r", 9, state_dir=tmp_path)
    assert loaded["attempts"] == 2
    assert receipts.clear("o/r", 9, state_dir=tmp_path) is True
    assert receipts.read("o/r", 9, state_dir=tmp_path) == {}


def test_select_gates_when_attempts_exhausted(tmp_path: Path) -> None:
    receipts.stamp("o/r", 9, state_dir=tmp_path, budget=1)
    out = select(
        _repairable(),
        enabled=True,
        triage_ran=True,
        state_dir=tmp_path,
        budget=1,
    )
    assert out["route"] == "fail_closed"
    assert out["reason"] == "pr_repair_budget_exhausted"
    assert out["parked"] is True
    assert out["attempts"] == 1
    assert out["budget"] == 1
    assert out["repairable"] is True
    assert "needs_human" not in out


def test_select_routes_repair_when_receipt_empty(tmp_path: Path) -> None:
    out = select(
        _repairable(),
        enabled=True,
        triage_ran=True,
        state_dir=tmp_path,
        budget=1,
    )
    assert out["route"] == "repair"
    assert out["attempts"] == 0
    assert out["parked"] is False
    assert "needs_human" not in out


def test_run_stamps_after_compose(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        f"""mode: dry-run
state:
  path: {tmp_path / 'state.jsonl'}
limits:
  max_repairs_per_tick: 1
repos:
  - name: o/r
    clone_path: {tmp_path / 'r'}
    enabled: true
""",
        encoding="utf-8",
    )
    calls: list[dict] = []

    def fake_compose(**kwargs: object) -> dict:
        calls.append(dict(kwargs))
        return {"ok": True, "result": {"terminal": "publish", "head_sha": "deadbeef"}}

    monkeypatch.setattr(
        "lokay.proc.run_parent_pr_repair_subflow.compose_pr_repair", fake_compose
    )
    selected = {
        "route": "repair",
        "repo": "o/r",
        "pr": 9,
        "branch": "ai/fix/9-x",
        "review": {"verdict": "request_changes"},
    }
    out = run_parent(selected, config_path=str(cfg), live=False)
    assert out["route"] == "completed"
    assert out["attempts"] == 1
    assert out["budget"] == 1
    assert out["parked"] is True
    assert len(calls) == 1
    stored = receipts.read("o/r", 9, state_dir=tmp_path)
    assert stored["attempts"] == 1
    assert stored["last_head_sha"] == "deadbeef"
    assert stored["parked"] is True

    gated = select(
        _repairable(),
        enabled=True,
        triage_ran=True,
        config_path=str(cfg),
    )
    assert gated["route"] == "fail_closed"
    assert gated["reason"] == "pr_repair_budget_exhausted"


def test_exhausted_select_does_not_call_compose(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipts.stamp("o/r", 9, state_dir=tmp_path, budget=1)
    selected = select(
        _repairable(),
        enabled=True,
        triage_ran=True,
        state_dir=tmp_path,
        budget=1,
    )
    assert selected["route"] == "fail_closed"

    def boom(**_kwargs: object) -> dict:
        raise AssertionError("compose must not run when budget exhausted")

    monkeypatch.setattr(
        "lokay.proc.run_parent_pr_repair_subflow.compose_pr_repair", boom
    )
    out = run_department(selected, config_path=None, live=False)
    assert out["route"] == "fail_closed"
    assert out["reason"] == "pr_repair_budget_exhausted"
    assert out["parked"] is True
    assert "needs_human" not in out


def test_run_stamps_on_compose_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        f"""mode: dry-run
state:
  path: {tmp_path / 'state.jsonl'}
repos:
  - name: o/r
    clone_path: {tmp_path / 'r'}
    enabled: true
""",
        encoding="utf-8",
    )

    def fake_compose(**_kwargs: object) -> dict:
        return {"ok": False, "error": "agent_failed", "terminal": "fail_closed"}

    monkeypatch.setattr(
        "lokay.proc.run_parent_pr_repair_subflow.compose_pr_repair", fake_compose
    )
    out = run_parent(
        {"repo": "o/r", "pr": 3, "branch": "ai/fix/3-x", "review": {}},
        config_path=str(cfg),
        live=False,
    )
    assert out["attempts"] == 1
    assert out["parked"] is True
    assert receipts.read("o/r", 3, state_dir=tmp_path)["attempts"] == 1
