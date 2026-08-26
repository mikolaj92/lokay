"""refresh_occupancy + select_implement: just-merged / live i2pr occupy the repo."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from lokay.passkit import io as pass_io
from lokay.proc import detach_issue_to_pr, refresh_occupancy
from lokay.proc.closeout_prs import run_closeout_prs
from lokay.proc.implementation_selection_catalog import run as _catalog
from lokay.proc.prepare_implementation_selection import prepare as _prepare_selection
from lokay.proc.persist_implementation_selection import persist as _persist_selection


def run_select_implement(*, pass_dir: str):
    prepared = _prepare_selection(pass_dir=pass_dir, slot_count=30)
    return _persist_selection(
        pass_dir=pass_dir, reduced=_catalog(prepared, pass_dir=pass_dir)
    )


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


def test_select_skips_repo_merged_this_pass(tmp_path):
    pass_dir = _pass(
        tmp_path,
        working={
            "ready_by_repo": {"mikolaj92/lokay": [{"number": 142, "title": "next"}]},
            "remaining_ready": 1,
            "merged_this_pass": ["mikolaj92/lokay"],
        },
    )
    result = run_select_implement(pass_dir=pass_dir)
    assert result["ok"] is True
    assert result["selected"] == 0
    implement = pass_io.read_json(pass_io.implement_path(pass_dir))
    assert implement["clean_repos"] == []
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    assert any(
        row.get("step") == "skip_ready_repo_occupied" for row in working["actions"]
    )


def test_select_skips_live_issue_to_pr_repo(tmp_path):
    pass_dir = _pass(
        tmp_path,
        working={
            "ready_by_repo": {
                "mikolaj92/lokay": [{"number": 59, "title": "in flight"}]
            },
            "remaining_ready": 1,
            "live_issue_to_pr_repos": ["mikolaj92/lokay"],
            "occupied_repos": ["mikolaj92/lokay"],
        },
    )
    result = run_select_implement(pass_dir=pass_dir)
    assert result["selected"] == 0
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    assert any(
        row.get("step") == "skip_ready_repo_occupied" for row in working["actions"]
    )


def _run_refresh(*, pass_dir, config_path=None, live=True):
    from lokay.proc.occupancy_catalog import SLOTS, run
    from lokay.proc.persist_occupancy_refresh import persist
    from lokay.proc.prepare_occupancy_refresh import prepare

    prepared = prepare(pass_dir=pass_dir, slot_count=SLOTS)
    return persist(
        pass_dir=pass_dir,
        reduced=run(
            prepared, pass_dir=pass_dir, config_path=config_path, live=live
        ),
    )


@pytest.mark.parametrize(
    ("pid_alive", "occupied", "started"),
    [(False, [], 0), (True, ["mikolaj92/lokay"], 1)],
)
def test_refresh_occupancy_uses_worker_liveness(
    tmp_path, monkeypatch, pid_alive, occupied, started
):
    """A historical start is not occupancy after its i2pr/pi process exits."""
    monkeypatch.setenv("HOME", str(tmp_path))
    cycle = tmp_path / ".lokay" / "cycle"
    cycle.mkdir(parents=True)
    (cycle / "a__one-2.json").write_text(
        json.dumps({"repo": "mikolaj92/lokay", "issue": 2, "pid": 987654}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        detach_issue_to_pr, "coding_live_for_issue", lambda _issue: False
    )
    monkeypatch.setattr(
        "lokay.proc.prepare_occupancy_refresh.live_issue_to_pr_receipts",
        lambda: detach_issue_to_pr.live_issue_to_pr_receipts(
            cycle, pid_alive=lambda _pid: pid_alive
        ),
    )
    monkeypatch.setattr(
        "lokay.proc.inspect_live_receipt_issue.run_proc",
        lambda fn, argv: (
            {"ok": True, "issue": {"state": "OPEN"}}
            if fn is __import__("lokay.proc.get_issue", fromlist=["main"]).main
            else {"ok": True, "prs": []}
        ),
    )
    pass_dir = _pass(
        tmp_path,
        working={
            "issue_to_pr_started": 1,
            "ready_by_repo": {"mikolaj92/lokay": [{"number": 3, "title": "next"}]},
            "remaining_ready": 1,
        },
    )

    out = _run_refresh(pass_dir=pass_dir, config_path=None, live=True)

    assert out["occupied_repos"] == occupied
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    assert working["occupied_repos"] == occupied
    assert working["issue_to_pr_started"] == started


def test_refresh_live_receipt_for_closed_issue_is_cleared(monkeypatch):
    from lokay.proc.terminate_closed_issue_worker import terminate
    from lokay.proc.clear_closed_issue_receipt import clear

    receipt = {"repo": "mikolaj92/lokay", "issue": 2, "pid": 9}
    killed = []
    cleared = []
    monkeypatch.setattr(
        "lokay.proc.terminate_closed_issue_worker.os.kill",
        lambda pid, sig: killed.append((pid, sig)),
    )
    monkeypatch.setattr(
        "lokay.proc.clear_closed_issue_receipt.clear_issue_to_pr_receipt",
        lambda row: not cleared.append(row),
    )
    terminated = terminate({"receipt": receipt, "repo": "mikolaj92/lokay", "issue": 2})
    out = clear(terminated)
    assert out["cleared"] is True and killed and cleared == [receipt]


def test_refresh_occupancy_failed_relist_blocks_repo(tmp_path, monkeypatch):
    pass_dir = _pass(
        tmp_path,
        working={
            "ready_by_repo": {"mikolaj92/lokay": [{"number": 2, "title": "next"}]},
            "remaining_ready": 1,
        },
    )
    monkeypatch.setattr(
        "lokay.proc.list_occupancy_pull_requests.run_proc",
        lambda fn, argv: {"ok": False, "error": "gh failed"},
    )
    monkeypatch.setattr(
        "lokay.proc.prepare_occupancy_refresh.live_issue_to_pr_receipts", lambda: []
    )
    out = _run_refresh(pass_dir=pass_dir, config_path=None, live=True)
    assert out["ok"] is True
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    assert working["pr_survey_failed"] == ["mikolaj92/lokay"]
    selected = run_select_implement(pass_dir=pass_dir)
    assert selected["selected"] == 0
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    assert any(
        row.get("step") == "skip_issue_to_pr_survey_failed"
        for row in working["actions"]
    )


def test_closeout_records_merged_this_pass(tmp_path):
    from lokay.proc.reduce_pr_closeout import reduce_state

    working = {
        "actions": [],
        "progress": 0,
        "prs_by_repo": {"mikolaj92/lokay": [{"number": 287, "labels": []}]},
    }
    row = {
        "ok": True,
        "repo": "mikolaj92/lokay",
        "still_open": False,
        "progress": 1,
        "repair_budget": 1,
    }
    out = reduce_state(prepared={"repair_budget": 1}, rows=[row], working=working)
    assert out["state"]["merged_this_pass"] == ["mikolaj92/lokay"]
    assert out["state"]["prs_by_repo"]["mikolaj92/lokay"] == []


def test_refresh_keeps_local_needs_review_park(tmp_path, monkeypatch):
    """GitHub lag must not un-park a same-pass ai:needs-review decision."""
    pass_dir = _pass(
        tmp_path,
        working={
            "prs_by_repo": {
                "mikolaj92/lokay": [
                    {
                        "number": 69,
                        "head_ref": "ai/fix/68-x",
                        "labels": ["ai:needs-review"],
                    }
                ]
            },
            "ready_by_repo": {"mikolaj92/lokay": [{"number": 70, "title": "next"}]},
            "remaining_ready": 1,
            "remaining_prs": 1,
            "actionable_prs": 0,
            "manual_prs": 1,
        },
    )
    monkeypatch.setattr(
        "lokay.proc.list_occupancy_pull_requests.run_proc",
        lambda fn, argv: {
            "ok": True,
            "prs": [
                {"number": 69, "head_ref": "ai/fix/68-x", "labels": ["ai:generated"]}
            ],
        },
    )
    monkeypatch.setattr(
        "lokay.proc.prepare_occupancy_refresh.live_issue_to_pr_receipts", lambda: []
    )
    out = _run_refresh(pass_dir=pass_dir, config_path=None, live=True)
    assert out["ok"] is True
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    parked = working["prs_by_repo"]["mikolaj92/lokay"][0]
    assert "ai:needs-review" in parked["labels"]
    selected = run_select_implement(pass_dir=pass_dir)
    assert selected["selected"] == 1
    implement = pass_io.read_json(pass_io.implement_path(pass_dir))
    assert implement["clean_repos"] == ["mikolaj92/lokay"]


def test_refresh_skips_empty_idle_repo(tmp_path, monkeypatch):
    """No leftover ready and no leftover PRs — do not spend a gh list."""
    pass_dir = _pass(
        tmp_path,
        begin={"repos": ["mikolaj92/lokay"]},
        working={"ready_by_repo": {"mikolaj92/lokay": []}},
    )
    called: list[str] = []

    def fake_run(fn, argv):
        called.append(argv[argv.index("--repo") + 1])
        return {"ok": True, "prs": []}

    monkeypatch.setattr("lokay.proc.list_occupancy_pull_requests.run_proc", fake_run)
    monkeypatch.setattr(
        "lokay.proc.prepare_occupancy_refresh.live_issue_to_pr_receipts", lambda: []
    )
    out = _run_refresh(pass_dir=pass_dir, config_path=None, live=True)
    assert out["ok"] is True
    assert called == []
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    assert working["prs_by_repo"]["mikolaj92/lokay"] == []
    skips = [a for a in working["actions"] if a.get("step") == "refresh_prs_skipped"]
    assert skips == [
        {"step": "refresh_prs_skipped", "repo": "mikolaj92/lokay", "reason": "no_ready"}
    ]


def test_refresh_failed_relist_keeps_snapshot(tmp_path, monkeypatch):
    """A 429 must not wipe a known open PR into a fake clear lane."""
    parked = {
        "number": 318,
        "head_ref": "ai/fix/32-x",
        "labels": ["ai:generated"],
    }
    pass_dir = _pass(
        tmp_path,
        working={
            "prs_by_repo": {"mikolaj92/lokay": [parked]},
            "ready_by_repo": {"mikolaj92/lokay": [{"number": 33, "title": "next"}]},
            "remaining_ready": 1,
            "remaining_prs": 1,
            "actionable_prs": 1,
        },
    )
    monkeypatch.setattr(
        "lokay.proc.list_occupancy_pull_requests.run_proc",
        lambda fn, argv: {"ok": False, "error": "gh rate limit exhausted"},
    )
    monkeypatch.setattr(
        "lokay.proc.prepare_occupancy_refresh.live_issue_to_pr_receipts", lambda: []
    )
    out = _run_refresh(pass_dir=pass_dir, config_path=None, live=True)
    assert out["ok"] is True
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    assert working["pr_survey_failed"] == ["mikolaj92/lokay"]
    assert working["prs_by_repo"]["mikolaj92/lokay"] == [parked]
    selected = run_select_implement(pass_dir=pass_dir)
    assert selected["selected"] == 0


def test_refresh_keeps_survey_error_on_skipped_failed_repo(tmp_path, monkeypatch):
    """An occupied 429 from survey_prs must stay on the board."""
    pass_dir = _pass(
        tmp_path,
        begin={"repos": ["mikolaj92/lokay"]},
        working={
            "merged_this_pass": ["mikolaj92/lokay"],
            "pr_survey_failed": ["mikolaj92/lokay"],
            "inbox_survey_failed": [],
            "ready_survey_failed": [],
            "ready_by_repo": {"mikolaj92/lokay": [{"number": 2, "title": "next"}]},
            "remaining_ready": 1,
            "survey_errors": 1,
        },
    )
    called: list[str] = []

    def fake_run(fn, argv):
        called.append(argv[argv.index("--repo") + 1])
        return {"ok": True, "prs": []}

    monkeypatch.setattr("lokay.proc.list_occupancy_pull_requests.run_proc", fake_run)
    monkeypatch.setattr(
        "lokay.proc.prepare_occupancy_refresh.live_issue_to_pr_receipts", lambda: []
    )
    out = _run_refresh(pass_dir=pass_dir, config_path=None, live=True)
    assert out["ok"] is True
    assert called == []
    assert out["survey_errors"] == 1
    assert out["probe_failed"] is True
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    assert working["pr_survey_failed"] == ["mikolaj92/lokay"]
    assert working["survey_errors"] == 1


def test_refresh_unknown_receipt_state_does_not_occupy_catalog(tmp_path, monkeypatch):
    """Stale/unreadable receipts are idle — they do not occupy every repo."""
    pass_dir = _pass(
        tmp_path,
        begin={"repos": ["mikolaj92/lokay", "a/two"]},
        working={
            "ready_by_repo": {
                "mikolaj92/lokay": [{"number": 1, "title": "one"}],
                "a/two": [{"number": 2, "title": "two"}],
            },
            "remaining_ready": 2,
        },
    )
    monkeypatch.setattr(
        "lokay.proc.prepare_occupancy_refresh.has_unreadable_issue_to_pr_receipts",
        lambda: True,
    )
    monkeypatch.setattr(
        "lokay.proc.prepare_occupancy_refresh.live_issue_to_pr_receipts", lambda: []
    )
    monkeypatch.setattr(
        "lokay.proc.list_occupancy_pull_requests.run_proc",
        lambda *_args, **_kwargs: {"ok": True, "prs": []},
    )

    out = _run_refresh(pass_dir=pass_dir, config_path=None, live=True)

    assert out["receipt_state_unknown"] is True
    assert out["occupied_repos"] == []
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    assert working["live_issue_to_pr_repos"] == []
    assert working["occupied_repos"] == []


def test_refresh_malformed_no_pid_receipt_does_not_occupy_catalog(
    tmp_path, monkeypatch
):
    """Partial no-PID objects stay unknown but do not occupy the catalog."""
    import json

    monkeypatch.setenv("HOME", str(tmp_path))
    cycle = tmp_path / ".lokay" / "cycle"
    cycle.mkdir(parents=True)
    (cycle / "owner__repo-9.json").write_text(
        json.dumps({"detached": True, "repo": "owner/repo", "issue": 9}),
        encoding="utf-8",
    )
    pass_dir = _pass(
        tmp_path,
        begin={"repos": ["owner/repo", "other/repo"]},
        working={
            "ready_by_repo": {
                "owner/repo": [{"number": 9, "title": "x"}],
                "other/repo": [{"number": 1, "title": "y"}],
            },
            "remaining_ready": 2,
        },
    )
    monkeypatch.setattr(
        "lokay.proc.list_occupancy_pull_requests.run_proc",
        lambda *_args, **_kwargs: {"ok": True, "prs": []},
    )

    out = _run_refresh(pass_dir=pass_dir, config_path=None, live=True)

    assert out["receipt_state_unknown"] is True
    assert out["occupied_repos"] == []
