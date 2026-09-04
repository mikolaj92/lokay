"""Hermetic two-pass factory truth: launch, detach, checks, merge, close.

GitHub is a local fixture. Status, work ledger, and pass receipts must agree.
A later stale false-negative cannot erase delivery.
"""

from __future__ import annotations

import json
from pathlib import Path

from lokay.child_harvest import harvest_fail_closed_children
from lokay.pass_receipt import read_pass_receipt
from lokay.passkit import io as pass_io
from lokay.proc.classify_pass_ceiling import classify as classify_ceiling
from lokay.proc.record_pass import run_record_pass
from lokay.proc.reduce_status_snapshot import reduce as reduce_status
from lokay.state import append_event
from lokay.work_units import project_work_units, status_work_units


REPO = "mikolaj92/reviewkit"
ISSUE = 308
PR = 309
WORK_ID = f"{REPO}#{ISSUE}"


def _cfg(tmp_path: Path) -> Path:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        f"""
mode: live
repos:
  - name: {REPO}
    clone_path: {tmp_path / "reviewkit"}
executor:
  enabled: true
  agent: grok
  command: grok
merge:
  enabled: true
  require_checks: true
limits:
  max_issue_to_pr_per_pass: 1
worktrees:
  root: {tmp_path / "wt"}
state:
  path: {tmp_path / "state.jsonl"}
""",
        encoding="utf-8",
    )
    (tmp_path / "reviewkit").mkdir()
    return cfg


def _begin(tmp_path: Path, name: str) -> Path:
    pass_dir = tmp_path / name
    pass_dir.mkdir()
    pass_io.write_json(
        pass_io.begin_path(pass_dir),
        {
            "merge_enabled": True,
            "require_checks": True,
            "require_llm_review": False,
            "max_issue_to_pr_per_pass": 1,
            "config_path": str(tmp_path / "config.yaml"),
            "state_path": str(tmp_path / "state.jsonl"),
        },
    )
    return pass_dir


def _github(issue_state: str, pr_merged: bool, checks: str) -> dict:
    return {
        "issue": {"repo": REPO, "number": ISSUE, "state": issue_state},
        "pr": {"repo": REPO, "number": PR, "merged": pr_merged, "checks": checks},
    }


def _status(tmp_path: Path, receipt: dict, units: list[dict], latest: dict | None) -> dict:
    return reduce_status(
        {
            "config": str(tmp_path / "config.yaml"),
            "mode": "live",
            "executor_enabled": True,
            "agent": "grok",
            "incident_repo": REPO,
            "merge_enabled": True,
            "require_checks": True,
            "require_llm_review": False,
            "max_issue_to_pr_per_pass": 1,
            "repos": [{"name": REPO, "enabled": True, "clone_path": str(tmp_path / "reviewkit")}],
        },
        {"lokay_ready": True, "blockers": [], "policy_notes": []},
        {"missing_clones": []},
        {
            "lease_ok": None,
            "lease_reason": "not_observed",
            "run_active": False,
            "run_observation_reason": "idle",
            "run_lease_path": None,
        },
        {"receipt": receipt},
        {"work_units": units, "latest_delivery": latest},
        {"repo_locks": []},
        {"graphs": ["factory_pass"]},
        {"preflight": None},
    )["snapshot"]


def test_two_pass_delivery_survives_stale_false_negative(tmp_path: Path):
    """Pass 1 launches. Detached worker finishes later. Pass 2 merges and closes.

    A stale condition_not_met after merge cannot regress GitHub or the ledger.
    """
    state = tmp_path / "state.jsonl"
    _cfg(tmp_path)
    github = _github("open", False, "pending")

    # Pass 1: serial launch. Worker is still detached. Not delivered.
    pass1 = _begin(tmp_path, "factory-pass-1")
    append_event(
        state,
        {
            "kind": "issue_to_pr",
            "repo": REPO,
            "issue": ISSUE,
            "run_id": "pass-1-launch",
            "work_state": "implementing",
            "delivered": False,
            "pid": 4242,
        },
    )
    launch = run_record_pass(
        pass_dir=str(pass1),
        issues={"result": {"route": "do", "launched": "started", "repo": REPO, "issue": ISSUE}},
    )
    assert launch["outcome"] == "new_pr"
    units = project_work_units(state)
    visible, latest = status_work_units(units)
    assert units[0]["work_id"] == WORK_ID
    assert units[0]["delivered"] is False
    assert units[0]["state"] == "implementing"
    assert latest is None
    receipt1 = read_pass_receipt(state_path=state)
    assert receipt1["outcome"] == "new_pr"
    snap1 = _status(tmp_path, receipt1, visible, latest)
    assert snap1["latest_delivery"] is None
    assert snap1["last_pass"]["outcome"] == "new_pr"
    assert github["issue"]["state"] == "open" and github["pr"]["merged"] is False

    # Ceiling during the wait must keep resume context, not stall-wipe.
    (tmp_path / "activity.json").write_text(
        json.dumps({"transitions": 1, "path": "executor_row", "work_id": WORK_ID, "repo": REPO}),
        encoding="utf-8",
    )
    ceiling = classify_ceiling(state_dir=tmp_path, elapsed_seconds=180)
    assert ceiling["reason"] == "ceiling_with_progress"
    assert ceiling["work_id"] == WORK_ID

    # Detached worker finishes after the launching pass. Checks still pending.
    append_event(
        state,
        {
            "kind": "issue_to_pr",
            "repo": REPO,
            "issue": ISSUE,
            "run_id": "pass-1-worker",
            "pr": PR,
            "branch": "ai/fix/308-reviewkit",
            "delivered": True,
            "work_state": "checks_pending",
        },
    )
    github = _github("open", False, "pending")
    units = project_work_units(state)
    assert units[0]["delivered"] is True
    assert units[0]["pr"] == PR
    # Delivery of the PR is not Done. Issue is still open; checks pending.
    assert github["issue"]["state"] == "open"
    assert github["pr"]["merged"] is False
    assert github["pr"]["checks"] == "pending"

    # Pass 2: checks go green, merge, close issue. That is Done.
    pass2 = _begin(tmp_path, "factory-pass-2")
    github = _github("closed", True, "success")
    append_event(
        state,
        {
            "kind": "issue_to_pr",
            "repo": REPO,
            "issue": ISSUE,
            "run_id": "pass-2-merge",
            "pr": PR,
            "delivered": True,
            "reason": "issue_closed",
            "work_state": "delivered",
        },
    )
    merge = run_record_pass(
        pass_dir=str(pass2),
        prs={"result": {"route": "pr", "triage": {"merged": True}, "merged": True}},
        issues={"result": {"route": "skip"}},
    )
    assert merge["outcome"] == "merge"
    units = project_work_units(state)
    visible, latest = status_work_units(units)
    receipt2 = read_pass_receipt(state_path=state)
    snap2 = _status(tmp_path, receipt2, visible, latest)
    assert receipt2["outcome"] == "merge"
    assert latest["work_id"] == WORK_ID
    assert latest["delivered"] is True
    assert latest["pr"] == PR
    assert snap2["latest_delivery"]["pr"] == PR
    assert snap2["last_pass"]["outcome"] == "merge"
    assert github["issue"]["state"] == "closed"
    assert github["pr"]["merged"] is True
    assert github["pr"]["checks"] == "success"
    # Ledger, receipt, status, and GitHub fixture agree on the same work unit.
    assert {latest["work_id"], snap2["latest_delivery"]["work_id"], WORK_ID} == {WORK_ID}

    # Later stale false-negative cannot regress the final outcome.
    append_event(
        state,
        {
            "kind": "issue_to_pr",
            "repo": REPO,
            "issue": ISSUE,
            "run_id": "pass-3-stale",
            "delivered": False,
            "stopped": True,
            "reason": "condition_not_met",
        },
    )
    stuck = harvest_fail_closed_children(
        {"issues": {}},
        state_path=state,
        cycle_dir=tmp_path / "cycle",
        is_live=lambda _pid: False,
        home=tmp_path,
    )
    units = project_work_units(state)
    visible, latest = status_work_units(units)
    snap3 = _status(tmp_path, receipt2, visible, latest)
    assert units[0]["delivered"] is True
    assert latest["pr"] == PR
    assert snap3["latest_delivery"]["pr"] == PR
    assert snap3["last_pass"]["outcome"] == "merge"
    assert github["issue"]["state"] == "closed"
    assert github["pr"]["merged"] is True
    assert stuck.get("issues", {}).get(WORK_ID) in (None, {})
