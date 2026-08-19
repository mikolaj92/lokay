"""Hermetic tests for lokay-closeout-pr (Fala composers mocked; no GitHub / git)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from lokay.proc import closeout_pr as closeout_pr
from lokay.proc import closeout_prs as closeout_prs
from lokay.proc import pr_checks as p_checks
from lokay.proc import stage_label as p_stage
from lokay.proc import unbounded_park as p_park
from lokay.proc.closeout_pr import main, run_closeout_pr
from lokay.passkit import io as pass_io

ROOT = Path(__file__).resolve().parents[1]


def _pr(**kwargs: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "number": 7,
        "head_ref": "ai/fix/7-x",
        "mergeable": "MERGEABLE",
        "labels": ["ai:generated"],
    }
    row.update(kwargs)
    return row


def _run(
    monkeypatch: pytest.MonkeyPatch,
    *,
    checks: dict[str, Any],
    pr: dict[str, Any] | None = None,
    triage: dict[str, Any] | None = None,
    repair: dict[str, Any] | None = None,
    tmp_path: Path,
    parked: list[list[str]] | None = None,
    **policy: Any,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    stages: list[str] = []
    triage_calls: list[dict[str, Any]] = []
    repair_calls: list[dict[str, Any]] = []

    def fake_proc(fn: Any, argv: list[str]) -> dict[str, Any]:
        if fn is p_checks.main:
            return {"ok": True, **checks}
        if fn is p_stage.main:
            stage = str(argv[argv.index("--stage") + 1])
            stages.append(stage)
            return {"ok": True, "applied": True, "stage": stage}
        if fn is p_park.main:
            if parked is not None:
                parked.append(list(argv))
            return {"ok": True, "applied": True, "removed": True}
        raise AssertionError(f"unexpected atom: {fn} {argv}")

    def fake_triage(**kwargs: Any) -> dict[str, Any]:
        triage_calls.append(kwargs)
        if triage is None:
            raise AssertionError("compose_pr_triage should not run")
        return dict(triage)

    def fake_repair(**kwargs: Any) -> dict[str, Any]:
        repair_calls.append(kwargs)
        if repair is None:
            raise AssertionError("compose_pr_repair should not run")
        return dict(repair)

    monkeypatch.setattr(closeout_pr, "run_proc", fake_proc)
    monkeypatch.setattr(closeout_pr, "compose_pr_triage", fake_triage)
    monkeypatch.setattr(closeout_pr, "compose_pr_repair", fake_repair)
    kwargs: dict[str, Any] = {
        "repo": "a/b",
        "pr": pr or _pr(),
        "config_path": None,
        "live": True,
        "merge_enabled": True,
        "require_checks": False,
        "repair_budget": 1,
        "executor_enabled": True,
        "branch_prefix": "ai/fix/",
        "stuck": {"issues": {}},
        "stuck_path": tmp_path / "stuck.json",
    }
    kwargs.update(policy)
    out = run_closeout_pr(**kwargs)
    return out, triage_calls, repair_calls, stages


def test_pending_waits_without_ci_waiting_label(monkeypatch, tmp_path):
    out, triage, repair, stages = _run(
        monkeypatch, checks={"status": "pending"}, tmp_path=tmp_path
    )
    assert out["ok"] is True
    assert out["route"] == "wait"
    assert out["reason"] == "checks_pending"
    assert out["still_open"] is True
    assert out["pending_checks"] == 1
    assert stages == []
    assert triage == []
    assert repair == []
    assert not any(a.get("step") == "stage_ci_waiting" for a in out["actions"])


def test_transient_checks_wait_without_pr_repair(monkeypatch, tmp_path):
    """A GitHub 503 is unknown state, not a reason to mutate a published tip."""
    out, triage, repair, stages = _run(
        monkeypatch, checks={"status": "pending", "green": False}, tmp_path=tmp_path
    )
    assert out["ok"] is True
    assert out["route"] == "wait"
    assert out["reason"] == "checks_pending"
    assert out["still_open"] is True
    assert out["pending_checks"] == 1
    assert repair == []
    assert triage == []
    assert stages == []


def test_failed_dispatches_pr_repair(monkeypatch, tmp_path):
    out, triage, repair, stages = _run(
        monkeypatch,
        checks={"status": "failed"},
        repair={"ok": True, "pushed": True},
        tmp_path=tmp_path,
    )
    assert out["ok"] is True
    assert out["route"] == "repair"
    assert out["reason"] == "checks_failed"
    assert out["still_open"] is True
    assert out["needs_repair"] == 1
    assert out["repair_budget"] == 0
    assert len(repair) == 1
    assert repair[0]["pr_number"] == 7
    assert triage == []
    assert stages == []
    assert any(a.get("step") == "pr_repair" for a in out["actions"])


def test_merge_dispatches_pr_triage(monkeypatch, tmp_path):
    out, triage, repair, stages = _run(
        monkeypatch,
        checks={"status": "passed", "merge_ok": True},
        triage={"ok": True, "merged": True},
        tmp_path=tmp_path,
    )
    assert out["ok"] is True
    assert out["route"] == "merge"
    assert out["still_open"] is False
    assert out["merged"] is True
    assert out["progress"] == 1
    assert out["remaining_closed"] == 1
    assert len(triage) == 1
    assert triage[0]["pr_number"] == 7
    assert repair == []
    assert stages == []
    assert any(a.get("step") == "pr_triage" for a in out["actions"])


def test_merged_closed_issue_is_parked(monkeypatch, tmp_path):
    parked: list[list[str]] = []
    out, triage, repair, stages = _run(
        monkeypatch,
        checks={"status": "passed", "merge_ok": True},
        triage={"ok": True, "merged": True},
        tmp_path=tmp_path,
        parked=parked,
    )
    assert out["ok"] is True
    assert out["still_open"] is False
    assert parked == [["--repo", "a/b", "--issue", "7"]]
    assert any(a.get("step") == "park_closed_issue" for a in out["actions"])


def test_open_issue_does_not_park(monkeypatch, tmp_path):
    parked: list[list[str]] = []
    out, triage, repair, stages = _run(
        monkeypatch,
        checks={"status": "pending"},
        tmp_path=tmp_path,
        parked=parked,
    )
    assert out["route"] == "wait"
    assert out["still_open"] is True
    assert parked == []


def test_skip_manual_does_not_touch_fala(monkeypatch, tmp_path):
    out, triage, repair, stages = _run(
        monkeypatch,
        checks={"status": "passed", "merge_ok": True},
        pr=_pr(labels=["ai:needs-review"]),
        tmp_path=tmp_path,
    )
    assert out["ok"] is True
    assert out["route"] == "skip"
    assert out["reason"] == "manual"
    assert out["still_open"] is True
    assert triage == []
    assert repair == []
    assert stages == []
    assert any(a.get("step") == "skip_manual_pr" for a in out["actions"])


def test_cli_pending_envelope(capsys, monkeypatch):
    def fake_proc(fn: Any, argv: list[str]) -> dict[str, Any]:
        if fn is p_checks.main:
            return {"ok": True, "status": "pending"}
        if fn is p_stage.main:
            return {"ok": True, "applied": True, "stage": "ci-waiting"}
        raise AssertionError(fn)

    monkeypatch.setattr(closeout_pr, "run_proc", fake_proc)
    monkeypatch.setattr(
        closeout_pr,
        "compose_pr_triage",
        lambda **_: (_ for _ in ()).throw(AssertionError("no triage")),
    )
    monkeypatch.setattr(
        closeout_pr,
        "compose_pr_repair",
        lambda **_: (_ for _ in ()).throw(AssertionError("no repair")),
    )
    code = main(
        [
            "--repo",
            "a/b",
            "--pr",
            "7",
            "--head-ref",
            "ai/fix/7-x",
            "--live",
            "--merge-enabled",
        ]
    )
    assert code == 0
    env = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert env["ok"] is True
    assert env["route"] == "wait"
    assert env["reason"] == "checks_pending"


def test_console_script_wired():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "lokay-closeout-pr" in text
    assert "lokay.proc.closeout_pr:main" in text


def test_closeout_pr_is_thin_glue():
    src = (ROOT / "src/lokay/proc/closeout_pr.py").read_text(encoding="utf-8")
    assert len(src.splitlines()) <= 100
    assert "run_pr_route" in src
    assert "compose_pr_triage" in src
    assert "compose_pr_repair" in src
    assert "decide_auto_merge" not in src
    effects = (ROOT / "src/lokay/closeout.py").read_text(encoding="utf-8")
    assert "compose_pr_" not in effects
    assert "fala" not in effects.lower()


def test_closeout_prs_is_thin_foreach():
    src = (ROOT / "src/lokay/proc/closeout_prs.py").read_text(encoding="utf-8")
    assert "run_closeout_pr" in src
    assert "compose_pr_triage" not in src
    assert "compose_pr_repair" not in src
    assert "run_pr_route" not in src
    assert "decide_auto_merge" not in src
    assert len(src.splitlines()) <= 110


def test_closeout_prs_foreach_recounts(tmp_path, monkeypatch):
    pass_dir = tmp_path / "pass"
    pass_dir.mkdir()
    pass_io.write_json(
        pass_io.begin_path(pass_dir),
        {
            "repos": ["a/one"],
            "repair_budget": 1,
            "executor_enabled": True,
            "merge_enabled": True,
            "require_checks": False,
            "branch_prefix": "ai/fix/",
            "stuck_path": str(tmp_path / "stuck.json"),
        },
    )
    pass_io.write_json(
        pass_io.working_path(pass_dir),
        {
            "actions": [],
            "progress": 0,
            "stuck": {"issues": {}},
            "prs_by_repo": {"a/one": [_pr(number=1), _pr(number=2)]},
            "remaining_prs": 2,
            "actionable_prs": 2,
            "manual_prs": 0,
            "pending_checks": 0,
            "no_checks_blocked": 0,
            "merge_conflicts": 0,
            "needs_repair": 0,
            "mergeable_green": 0,
            "merge_disabled": 0,
            "review_limbo": 0,
        },
    )
    seen: list[int] = []

    def fake_atom(**kwargs: Any) -> dict[str, Any]:
        num = int(kwargs["pr"]["number"])
        seen.append(num)
        merged = num == 1
        return {
            "ok": True,
            "still_open": not merged,
            "actions": [{"step": "pr_triage", "pr": num}] if merged else [],
            "repair_budget": kwargs["repair_budget"],
            "progress": 1 if merged else 0,
            "remaining_closed": 1 if merged else 0,
            "pending_checks": 0,
            "no_checks_blocked": 0,
            "merge_conflicts": 0,
            "needs_repair": 0,
            "mergeable_green": 0,
            "merge_disabled": 0,
            "review_limbo": 0,
        }

    monkeypatch.setattr(closeout_prs, "run_closeout_pr", fake_atom)
    out = closeout_prs.run_closeout_prs(
        pass_dir=str(pass_dir), config_path=None, live=True
    )
    assert seen == [1, 2]
    assert out["ok"] is True
    assert out["remaining_prs"] == 1
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    assert [pr["number"] for pr in working["prs_by_repo"]["a/one"]] == [2]
    assert working["progress"] == 1
    assert working["actionable_prs"] == 1
    assert working["merged_this_pass"] == ["a/one"]
