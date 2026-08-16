"""refresh_occupancy + select_implement: just-merged / live i2pr occupy the repo."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lokay.passkit import io as pass_io
from lokay.proc import refresh_occupancy
from lokay.proc.closeout_prs import run_closeout_prs
from lokay.proc.select_implement import run_select_implement


def _pass(tmp_path: Path, *, working: dict[str, Any], begin: dict[str, Any] | None = None) -> str:
    pass_dir = tmp_path / "pass"
    pass_dir.mkdir()
    base_begin = {
        "live": True,
        "issue_budget": 1,
        "executor_enabled": True,
        "merge_enabled": True,
        "mode": "live",
        "repos": ["a/one"],
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
            "ready_by_repo": {"a/one": [{"number": 142, "title": "next"}]},
            "remaining_ready": 1,
            "merged_this_pass": ["a/one"],
        },
    )
    result = run_select_implement(pass_dir=pass_dir)
    assert result["ok"] is True
    assert result["selected"] == 0
    implement = pass_io.read_json(pass_io.implement_path(pass_dir))
    assert implement["clean_repos"] == []
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    assert any(row.get("step") == "skip_ready_repo_occupied" for row in working["actions"])


def test_select_skips_live_issue_to_pr_repo(tmp_path):
    pass_dir = _pass(
        tmp_path,
        working={
            "ready_by_repo": {"a/one": [{"number": 59, "title": "in flight"}]},
            "remaining_ready": 1,
            "live_issue_to_pr_repos": ["a/one"],
            "occupied_repos": ["a/one"],
        },
    )
    result = run_select_implement(pass_dir=pass_dir)
    assert result["selected"] == 0
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    assert any(row.get("step") == "skip_ready_repo_occupied" for row in working["actions"])


def test_refresh_occupancy_unions_merged_and_live(tmp_path, monkeypatch):
    pass_dir = _pass(
        tmp_path,
        begin={"repos": ["a/one", "a/two"]},
        working={
            "merged_this_pass": ["a/one"],
            "ready_by_repo": {
                "a/one": [{"number": 2, "title": "next"}],
                "a/two": [{"number": 3, "title": "other"}],
            },
            "remaining_ready": 2,
        },
    )

    def fake_run(fn, argv):
        repo = argv[argv.index("--repo") + 1]
        return {"ok": True, "prs": []}

    monkeypatch.setattr(refresh_occupancy, "run_proc", fake_run)
    monkeypatch.setattr(
        refresh_occupancy,
        "live_issue_to_pr_receipts",
        lambda: [{"repo": "a/two", "issue": 3, "pid": 9}],
    )
    out = refresh_occupancy.run_refresh_occupancy(
        pass_dir=pass_dir, config_path=None, live=True
    )
    assert out["ok"] is True
    assert out["merged_this_pass"] == ["a/one"]
    assert out["live_issue_to_pr_repos"] == ["a/two"]
    assert out["occupied_repos"] == ["a/one", "a/two"]
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    assert working["occupied_repos"] == ["a/one", "a/two"]
    assert working["prs_by_repo"] == {"a/one": [], "a/two": []}

    selected = run_select_implement(pass_dir=pass_dir)
    assert selected["selected"] == 0
    implement = pass_io.read_json(pass_io.implement_path(pass_dir))
    assert implement["clean_repos"] == []


def test_refresh_occupancy_failed_relist_blocks_repo(tmp_path, monkeypatch):
    pass_dir = _pass(
        tmp_path,
        working={
            "ready_by_repo": {"a/one": [{"number": 2, "title": "next"}]},
            "remaining_ready": 1,
        },
    )
    monkeypatch.setattr(
        refresh_occupancy,
        "run_proc",
        lambda fn, argv: {"ok": False, "error": "gh failed"},
    )
    monkeypatch.setattr(refresh_occupancy, "live_issue_to_pr_receipts", lambda: [])
    out = refresh_occupancy.run_refresh_occupancy(
        pass_dir=pass_dir, config_path=None, live=True
    )
    assert out["ok"] is True
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    assert working["pr_survey_failed"] == ["a/one"]
    selected = run_select_implement(pass_dir=pass_dir)
    assert selected["selected"] == 0
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    assert any(
        row.get("step") == "skip_issue_to_pr_survey_failed" for row in working["actions"]
    )


def test_closeout_records_merged_this_pass(tmp_path, monkeypatch):
    pass_dir = _pass(
        tmp_path,
        working={
            "prs_by_repo": {
                "a/one": [{"number": 287, "head_ref": "ai/fix/141-x", "labels": ["ai:generated"]}]
            },
            "remaining_prs": 1,
            "actionable_prs": 1,
            "pending_checks": 0,
            "no_checks_blocked": 0,
            "merge_conflicts": 0,
            "needs_repair": 0,
            "mergeable_green": 0,
            "merge_disabled": 0,
            "review_limbo": 0,
            "stuck": {"issues": {}},
        },
        begin={
            "repos": ["a/one"],
            "repair_budget": 1,
            "stuck_path": str(tmp_path / "stuck.json"),
            "require_checks": False,
            "branch_prefix": "ai/fix/",
        },
    )

    def fake_atom(**kwargs: Any) -> dict[str, Any]:
        return {
            "ok": True,
            "still_open": False,
            "actions": [{"step": "pr_triage", "pr": 287}],
            "repair_budget": kwargs["repair_budget"],
            "progress": 1,
            "remaining_closed": 1,
            "pending_checks": 0,
            "no_checks_blocked": 0,
            "merge_conflicts": 0,
            "needs_repair": 0,
            "mergeable_green": 0,
            "merge_disabled": 0,
            "review_limbo": 0,
        }

    monkeypatch.setattr("lokay.proc.closeout_prs.run_closeout_pr", fake_atom)
    out = run_closeout_prs(pass_dir=pass_dir, config_path=None, live=True)
    assert out["ok"] is True
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    assert working["merged_this_pass"] == ["a/one"]
    assert working["prs_by_repo"]["a/one"] == []


def test_refresh_keeps_local_needs_review_park(tmp_path, monkeypatch):
    """GitHub lag must not un-park a same-pass ai:needs-review decision."""
    pass_dir = _pass(
        tmp_path,
        working={
            "prs_by_repo": {
                "a/one": [
                    {
                        "number": 69,
                        "head_ref": "ai/fix/68-x",
                        "labels": ["ai:needs-review"],
                    }
                ]
            },
            "ready_by_repo": {"a/one": [{"number": 70, "title": "next"}]},
            "remaining_ready": 1,
            "remaining_prs": 1,
            "actionable_prs": 0,
            "manual_prs": 1,
        },
    )
    monkeypatch.setattr(
        refresh_occupancy,
        "run_proc",
        lambda fn, argv: {
            "ok": True,
            "prs": [{"number": 69, "head_ref": "ai/fix/68-x", "labels": ["ai:generated"]}],
        },
    )
    monkeypatch.setattr(refresh_occupancy, "live_issue_to_pr_receipts", lambda: [])
    out = refresh_occupancy.run_refresh_occupancy(
        pass_dir=pass_dir, config_path=None, live=True
    )
    assert out["ok"] is True
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    parked = working["prs_by_repo"]["a/one"][0]
    assert "ai:needs-review" in parked["labels"]
    selected = run_select_implement(pass_dir=pass_dir)
    assert selected["selected"] == 1
    implement = pass_io.read_json(pass_io.implement_path(pass_dir))
    assert implement["clean_repos"] == ["a/one"]
