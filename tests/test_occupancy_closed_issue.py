"""Live i2pr pid + GitHub CLOSED does not occupy the repo."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lokay.passkit import io as pass_io
from lokay.proc import repo_mutex
from lokay.proc.issue_delivery_occupancy import live_issue_to_pr_receipts
from lokay.proc.prepare_implementation_selection import prepare as _prepare_selection
from lokay.proc.implementation_selection_catalog import run as _catalog
from lokay.proc.persist_implementation_selection import persist as _persist_selection
from lokay.proc.reduce_occupancy_facts import reduce_state as reduce_facts
from lokay.proc.seed_factory_occupancy import run as seed_occupancy


def _pass(
    tmp_path: Path, *, working: dict[str, Any], begin: dict[str, Any] | None = None
) -> str:
    pass_dir = tmp_path / "pass"
    pass_dir.mkdir()
    base_begin = {
        "live": True,
        "issue_budget": 1,
        "executor_enabled": True,
        "merge_enabled": True,
        "mode": "live",
        "repos": ["mikolaj92/lokay"],
        "planned": [],
        "stuck_path": "",
    }
    if begin:
        base_begin.update(begin)
    pass_io.write_json(pass_io.begin_path(pass_dir), base_begin)
    base_working = {
        "actions": [],
        "progress": 0,
        "prs_by_repo": {},
        "ready_by_repo": {},
        "pr_survey_failed": [],
        "remaining_inbox": 0,
        "remaining_ready": 0,
        "remaining_prs": 0,
        "actionable_prs": 0,
        "manual_prs": 0,
        "mergeable_green": 0,
        "needs_repair": 0,
        "review_limbo": 0,
        "pending_checks": 0,
        "survey_errors": 0,
        "merged_this_pass": [],
        "occupied_repos": [],
        "live_issue_to_pr_repos": [],
    }
    base_working.update(working)
    pass_io.write_json(pass_io.working_path(pass_dir), base_working)
    return str(pass_dir)


def _write_live_receipt(tmp_path: Path, *, issue: int = 857) -> Path:
    cycle = tmp_path / ".lokay" / "cycle"
    cycle.mkdir(parents=True)
    path = cycle / f"mikolaj92__lokay-{issue}.json"
    path.write_text(
        json.dumps({"repo": "mikolaj92/lokay", "issue": issue, "pid": 35576}),
        encoding="utf-8",
    )
    return cycle


def test_live_pid_closed_issue_is_not_a_live_receipt(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(
        "lokay.proc.issue_delivery_occupancy.coding_live_for_issue",
        lambda _issue: False,
    )
    _write_live_receipt(tmp_path)
    live = live_issue_to_pr_receipts(
        pid_alive=lambda _pid: True,
        issue_closed=lambda repo, issue: repo == "mikolaj92/lokay" and issue == 857,
    )
    assert live == []


def test_live_pid_open_issue_still_occupies(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(
        "lokay.proc.issue_delivery_occupancy.coding_live_for_issue",
        lambda _issue: False,
    )
    _write_live_receipt(tmp_path, issue=861)
    live = live_issue_to_pr_receipts(
        pid_alive=lambda _pid: True,
        issue_closed=lambda *_args, **_kwargs: False,
    )
    assert [row["issue"] for row in live] == [861]


def test_closed_probe_failure_keeps_occupancy(tmp_path, monkeypatch):
    """Same fail-closed as repo_mutex: unknown GitHub state still holds."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(
        "lokay.proc.issue_delivery_occupancy.coding_live_for_issue",
        lambda _issue: False,
    )
    monkeypatch.setattr(
        "lokay.proc.repo_mutex.subprocess.run",
        lambda *_args, **_kwargs: type(
            "Completed", (), {"returncode": 1, "stdout": ""}
        )(),
    )
    _write_live_receipt(tmp_path)
    live = live_issue_to_pr_receipts(pid_alive=lambda _pid: True)
    assert [row["issue"] for row in live] == [857]


def test_closed_live_receipt_uses_repo_mutex_closed_fact(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(
        "lokay.proc.issue_delivery_occupancy.coding_live_for_issue",
        lambda _issue: False,
    )
    seen = []

    def closed(repo: str, issue: int) -> bool:
        seen.append((repo, issue))
        return True

    monkeypatch.setattr(repo_mutex, "_issue_is_closed", closed)
    _write_live_receipt(tmp_path)
    assert live_issue_to_pr_receipts(pid_alive=lambda _pid: True) == []
    assert seen == [("mikolaj92/lokay", 857)]


def test_closed_unclear_catalog_fact_does_not_occupy():
    out = reduce_facts(
        prepared={"merged": [], "receipt_state_unknown": False},
        merged_clear={"cleared": []},
        results=[
            {
                "route": "closed",
                "repo": "mikolaj92/lokay",
                "receipt": {"repo": "mikolaj92/lokay", "issue": 857, "pid": 35576},
                "cleared": False,
            }
        ],
    )
    assert out["live_repos"] == []
    assert out["occupied"] == []


def test_seed_and_select_start_next_open_when_live_pid_issue_is_closed(
    tmp_path, monkeypatch
):
    """factory_begin occupancy + select_implement: CLOSED zombie does not freeze 861."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(
        "lokay.proc.issue_delivery_occupancy.coding_live_for_issue",
        lambda _issue: False,
    )
    monkeypatch.setattr(
        "lokay.proc.issue_delivery_occupancy.is_live_issue_to_pr_pid",
        lambda _pid: True,
    )
    monkeypatch.setattr(repo_mutex, "_issue_is_closed", lambda _repo, _issue: True)
    _write_live_receipt(tmp_path)
    seeded = seed_occupancy(
        {
            "working": {
                "ready_by_repo": {
                    "mikolaj92/lokay": [{"number": 861, "title": "next open"}]
                },
                "occupied_repos": [],
                "live_issue_to_pr_repos": [],
            }
        }
    )
    working = seeded["working"]
    assert working["occupied_repos"] == []
    assert working["live_issue_to_pr_repos"] == []

    pass_dir = _pass(
        tmp_path,
        working={
            "ready_by_repo": working["ready_by_repo"],
            "remaining_ready": 1,
            "occupied_repos": working["occupied_repos"],
            "live_issue_to_pr_repos": working["live_issue_to_pr_repos"],
        },
    )
    selected = _persist_selection(
        pass_dir=pass_dir,
        reduced=_catalog(_prepare_selection(pass_dir=pass_dir, slot_count=30), pass_dir=pass_dir),
    )
    assert selected["selected"] == 1
    implement = pass_io.read_json(pass_io.implement_path(pass_dir))
    assert implement["clean_repos"] == ["mikolaj92/lokay"]


def test_seed_occupies_when_live_pid_issue_is_open(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(
        "lokay.proc.issue_delivery_occupancy.coding_live_for_issue",
        lambda _issue: False,
    )
    monkeypatch.setattr(
        "lokay.proc.issue_delivery_occupancy.is_live_issue_to_pr_pid",
        lambda _pid: True,
    )
    monkeypatch.setattr(repo_mutex, "_issue_is_closed", lambda _repo, _issue: False)
    _write_live_receipt(tmp_path, issue=861)
    seeded = seed_occupancy(
        {"working": {"ready_by_repo": {}, "occupied_repos": []}}
    )
    assert seeded["working"]["occupied_repos"] == ["mikolaj92/lokay"]
    assert seeded["working"]["live_issue_to_pr_repos"] == ["mikolaj92/lokay"]
