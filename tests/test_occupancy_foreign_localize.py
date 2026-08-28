"""Live i2pr pid + leftover / foreign localize does not occupy the repo."""

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
from lokay.proc.seed_factory_occupancy import run as seed_occupancy


# Same leftover #333 payload as tests/test_localize.py (#878).
LEFTOVER_333 = {
    "paths": [
        "src/lokay/proc/factory_begin.py",
        "hot.py",
        "lokay/proc/factory_begin.py",
        "tests/test_hot_repos.py",
    ],
    "source": "agent",
    "worktree": (
        "/Users/mini-m4-main/.lokay/worktrees/mikolaj92__lokay/"
        "ai__fix__333-factory_begin-cold-survey-musi-pokry-sko-1ddbe4a4"
    ),
}


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


def _write_live_receipt(tmp_path: Path, *, issue: int = 865) -> Path:
    cycle = tmp_path / ".lokay" / "cycle"
    cycle.mkdir(parents=True, exist_ok=True)
    path = cycle / f"mikolaj92__lokay-{issue}.json"
    path.write_text(
        json.dumps({"repo": "mikolaj92/lokay", "issue": issue, "pid": 35576}),
        encoding="utf-8",
    )
    return cycle


def _write_worktree_localize(tmp_path: Path, *, issue: int, payload: dict) -> Path:
    wt = (
        tmp_path
        / ".lokay"
        / "worktrees"
        / "mikolaj92__lokay"
        / f"ai__fix__{issue}-plugin-sieve"
    )
    loc = wt / ".lokay"
    loc.mkdir(parents=True)
    (loc / "localize.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return wt


def _this_issue_payload(issue: int, worktree: Path) -> dict:
    return {
        "paths": ["src/lokay/localize.py"],
        "source": "deterministic",
        "issue": issue,
        "worktree": str(worktree),
    }


def test_live_pid_leftover_333_is_not_a_live_receipt(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(
        "lokay.proc.issue_delivery_occupancy.coding_live_for_issue",
        lambda _issue: False,
    )
    _write_live_receipt(tmp_path, issue=865)
    _write_worktree_localize(tmp_path, issue=865, payload=LEFTOVER_333)
    live = live_issue_to_pr_receipts(
        pid_alive=lambda _pid: True,
        issue_closed=lambda *_args, **_kwargs: False,
    )
    assert live == []


def test_live_pid_this_issue_localize_still_occupies(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(
        "lokay.proc.issue_delivery_occupancy.coding_live_for_issue",
        lambda _issue: False,
    )
    _write_live_receipt(tmp_path, issue=865)
    wt = _write_worktree_localize(
        tmp_path, issue=865, payload={"paths": ["src/a.py"]}
    )
    (wt / ".lokay" / "localize.json").write_text(
        json.dumps(_this_issue_payload(865, wt)),
        encoding="utf-8",
    )
    live = live_issue_to_pr_receipts(
        pid_alive=lambda _pid: True,
        issue_closed=lambda *_args, **_kwargs: False,
    )
    assert [row["issue"] for row in live] == [865]


def test_zero_worktree_does_not_occupy(tmp_path, monkeypatch):
    """Live pid with no worktree for this issue frees the repo (#891)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(
        "lokay.proc.issue_delivery_occupancy.coding_live_for_issue",
        lambda _issue: False,
    )
    _write_live_receipt(tmp_path, issue=865)
    live = live_issue_to_pr_receipts(
        pid_alive=lambda _pid: True,
        issue_closed=lambda *_args, **_kwargs: False,
    )
    assert live == []


def test_several_worktrees_keep_occupancy(tmp_path, monkeypatch):
    """Ambiguous worktree match stays fail-closed occupied."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(
        "lokay.proc.issue_delivery_occupancy.coding_live_for_issue",
        lambda _issue: False,
    )
    _write_live_receipt(tmp_path, issue=865)
    _write_worktree_localize(tmp_path, issue=865, payload=LEFTOVER_333)
    # Second corner for the same issue number (ambiguous).
    wt2 = (
        tmp_path
        / ".lokay"
        / "worktrees"
        / "mikolaj92__lokay"
        / f"ai__fix__{865}-second-corner"
    )
    (wt2 / ".lokay").mkdir(parents=True)
    (wt2 / ".lokay" / "localize.json").write_text(
        json.dumps(LEFTOVER_333, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    live = live_issue_to_pr_receipts(
        pid_alive=lambda _pid: True,
        issue_closed=lambda *_args, **_kwargs: False,
    )
    assert [row["issue"] for row in live] == [865]


def test_unreadable_localize_keeps_occupancy(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(
        "lokay.proc.issue_delivery_occupancy.coding_live_for_issue",
        lambda _issue: False,
    )
    _write_live_receipt(tmp_path, issue=865)
    wt = _write_worktree_localize(tmp_path, issue=865, payload=LEFTOVER_333)
    (wt / ".lokay" / "localize.json").write_text("{not-json", encoding="utf-8")
    live = live_issue_to_pr_receipts(
        pid_alive=lambda _pid: True,
        issue_closed=lambda *_args, **_kwargs: False,
    )
    assert [row["issue"] for row in live] == [865]


def test_missing_issue_id_does_not_occupy(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(
        "lokay.proc.issue_delivery_occupancy.coding_live_for_issue",
        lambda _issue: False,
    )
    _write_live_receipt(tmp_path, issue=865)
    _write_worktree_localize(
        tmp_path, issue=865, payload={"paths": ["src/a.py"], "source": "deterministic"}
    )
    live = live_issue_to_pr_receipts(
        pid_alive=lambda _pid: True,
        issue_closed=lambda *_args, **_kwargs: False,
    )
    assert live == []


def test_seed_and_select_start_next_when_live_pid_has_zero_worktree(
    tmp_path, monkeypatch
):
    """factory_begin occupancy + select_implement: zero worktree does not freeze 865."""
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
    _write_live_receipt(tmp_path, issue=865)
    seeded = seed_occupancy(
        {
            "working": {
                "ready_by_repo": {
                    "mikolaj92/lokay": [{"number": 865, "title": "plugin"}]
                },
                "occupied_repos": [],
                "live_issue_to_pr_repos": [],
            }
        }
    )
    working = seeded["working"]
    assert working["occupied_repos"] == []
    assert working["live_issue_to_pr_repos"] == []


def test_seed_and_select_start_next_when_live_pid_has_leftover_localize(
    tmp_path, monkeypatch
):
    """factory_begin occupancy + select_implement: leftover #333 does not freeze 865."""
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
    _write_live_receipt(tmp_path, issue=865)
    _write_worktree_localize(tmp_path, issue=865, payload=LEFTOVER_333)
    seeded = seed_occupancy(
        {
            "working": {
                "ready_by_repo": {
                    "mikolaj92/lokay": [{"number": 865, "title": "plugin"}]
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
        reduced=_catalog(
            _prepare_selection(pass_dir=pass_dir, slot_count=30), pass_dir=pass_dir
        ),
    )
    assert selected["selected"] == 1
    implement = pass_io.read_json(pass_io.implement_path(pass_dir))
    assert implement["clean_repos"] == ["mikolaj92/lokay"]
