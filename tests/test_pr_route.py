"""Hermetic tests for lokay-pr-route (no GitHub / git / Fala)."""

from __future__ import annotations

import json
from pathlib import Path

from lokay.proc.pr_route import main, run_pr_route

ROOT = Path(__file__).resolve().parents[1]


def test_green_routes_merge():
    out = run_pr_route(
        checks={"status": "passed", "merge_ok": True},
        merge_enabled=True,
    )
    assert out["ok"] is True
    assert out["route"] == "merge"
    assert out["reason"] == "approve_green"
    assert out["merge_ok"] is True


def test_pending_routes_wait():
    out = run_pr_route(checks={"status": "pending"}, merge_enabled=True)
    assert out["ok"] is True
    assert out["route"] == "wait"
    assert out["reason"] == "checks_pending"
    assert out["waiting"] is True


def test_failed_routes_repair():
    out = run_pr_route(checks={"status": "failed"}, merge_enabled=True)
    assert out["ok"] is True
    assert out["route"] == "repair"
    assert out["reason"] == "checks_failed"
    assert out["repairable"] is True


def test_merge_disabled_routes_wait():
    out = run_pr_route(
        checks={"status": "passed", "merge_ok": True},
        merge_enabled=False,
    )
    assert out["ok"] is True
    assert out["route"] == "wait"
    assert out["reason"] == "merge_disabled"
    assert out["waiting"] is True


def test_needs_review_routes_skip():
    out = run_pr_route(
        checks={"status": "passed", "merge_ok": True},
        merge_enabled=True,
        labels=["ai:generated", "ai:needs-review"],
    )
    assert out["ok"] is True
    assert out["route"] == "skip"
    assert out["reason"] == "ai_needs_review_label"
    assert out["needs_review"] is True


def test_pending_still_waits_when_merge_disabled():
    """Closeout must stage ci-waiting even while merge.enabled is off."""
    out = run_pr_route(checks={"status": "pending"}, merge_enabled=False)
    assert out["route"] == "wait"
    assert out["reason"] == "checks_pending"


def test_failed_still_repairs_when_merge_disabled():
    out = run_pr_route(checks={"status": "failed"}, merge_enabled=False)
    assert out["route"] == "repair"
    assert out["reason"] == "checks_failed"


def test_missing_checks_fail_closed():
    out = run_pr_route(checks=None, merge_enabled=True)
    assert out["ok"] is False
    assert "checks" in str(out.get("error") or "")


def test_cli_green_envelope(capsys):
    code = main(
        [
            "--merge-enabled",
            "--checks",
            json.dumps({"status": "passed", "merge_ok": True}),
        ]
    )
    assert code == 0
    env = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert env["ok"] is True
    assert env["route"] == "merge"


def test_console_script_wired():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "lokay-pr-route" in text
    assert "lokay.proc.pr_route:main" in text


def test_closeout_calls_route_atom_not_inline_matrix():
    src = (ROOT / "src/lokay/proc/closeout_pr.py").read_text(encoding="utf-8")
    assert "run_pr_route" in src
    assert "decide_auto_merge" not in src
    assert "can_merge" not in src
