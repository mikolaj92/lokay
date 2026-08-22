"""select_implement: parked needs-review must not PR-first-block ready work."""

from __future__ import annotations

import pytest

from pathlib import Path
from typing import Any

from lokay.passkit import io as pass_io
from lokay.proc.compute_health import run_compute_health
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
    }
    base_working.update(working)
    pass_io.write_json(pass_io.working_path(pass_dir), base_working)
    return str(pass_dir)


@pytest.mark.skip(reason="obsolete single-repository mill contract")
def test_mini_mill_selects_lokay_but_skips_product_repo(tmp_path):
    pass_dir = _pass(
        tmp_path,
        begin={"repos": ["mikolaj92/Temida", "mikolaj92/lokay"]},
        working={
            "ready_by_repo": {
                "mikolaj92/Temida": [{"number": 10, "title": "product work"}],
                "mikolaj92/lokay": [{"number": 414, "title": "mill work"}],
            },
            "remaining_ready": 2,
        },
    )

    result = run_select_implement(pass_dir=pass_dir)

    assert result["ok"] is True
    assert result["selected"] == 1
    implement = pass_io.read_json(pass_io.implement_path(pass_dir))
    assert implement["clean_repos"] == ["mikolaj92/lokay"]
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    assert any(
        row.get("step") == "skip_issue_to_pr_outside_mini_scope"
        and row.get("repo") == "mikolaj92/Temida"
        for row in working["actions"]
    )


def test_blocked_ready_issue_is_not_selected_for_issue_to_pr(tmp_path):
    pass_dir = _pass(
        tmp_path,
        working={
            "ready_by_repo": {"a/one": [{"number": 192, "title": "blocked"}]},
            "remaining_ready": 1,
            "stuck": {"issues": {"a/one#192": {"blocked": True}}},
        },
    )
    result = run_select_implement(pass_dir=pass_dir)
    assert result["ok"] is True
    assert result["selected"] == 0
    implement = pass_io.read_json(pass_io.implement_path(pass_dir))
    assert implement["clean_repos"] == []
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    assert working["ready_by_repo"]["a/one"] == []
    assert working["remaining_ready"] == 0
    assert any(row.get("step") == "skip_stuck" for row in working["actions"])


def test_blocked_ready_issue_is_read_from_stuck_ledger(tmp_path):
    stuck_path = tmp_path / "stuck.json"
    stuck_path.write_text(
        '{"issues": {"a/one#192": {"blocked": true}}}\n', encoding="utf-8"
    )
    pass_dir = _pass(
        tmp_path,
        begin={"stuck_path": str(stuck_path)},
        working={
            "ready_by_repo": {"a/one": [{"number": 192, "title": "blocked"}]},
            "remaining_ready": 1,
        },
    )
    result = run_select_implement(pass_dir=pass_dir)
    assert result["selected"] == 0
    assert pass_io.read_json(pass_io.implement_path(pass_dir))["clean_repos"] == []


def test_manual_needs_review_does_not_block_same_repo_ready(tmp_path):
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
            "ready_by_repo": {
                "a/one": [{"number": 70, "title": "next ready"}]
            },
            "remaining_ready": 1,
            "remaining_prs": 1,
            "actionable_prs": 0,
            "manual_prs": 1,
        },
    )
    result = run_select_implement(pass_dir=pass_dir)
    assert result["ok"] is True
    assert result["selected"] == 1
    implement = pass_io.read_json(pass_io.implement_path(pass_dir))
    assert implement["clean_repos"] == ["a/one"]
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    assert not any(
        row.get("step") == "skip_ready_open_ai_pr" for row in working.get("actions") or []
    )


def test_actionable_ai_pr_still_blocks_same_repo_ready(tmp_path):
    pass_dir = _pass(
        tmp_path,
        working={
            "prs_by_repo": {
                "a/one": [{"number": 1, "head_ref": "ai/fix/1-x", "labels": ["ai:generated"]}]
            },
            "ready_by_repo": {"a/one": [{"number": 2, "title": "next"}]},
            "remaining_ready": 1,
            "actionable_prs": 1,
        },
    )
    result = run_select_implement(pass_dir=pass_dir)
    assert result["ok"] is True
    assert result["selected"] == 0
    implement = pass_io.read_json(pass_io.implement_path(pass_dir))
    assert implement["clean_repos"] == []
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    assert any(
        row.get("step") == "skip_ready_open_ai_pr" for row in working.get("actions") or []
    )


def test_compute_health_parked_needs_review_only_is_waiting_not_stall(tmp_path):
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
            "ready_by_repo": {},
            "remaining_ready": 0,
            "remaining_prs": 1,
            "actionable_prs": 0,
            "manual_prs": 1,
            "actions": [{"step": "skip_manual_pr", "pr": 69}],
        },
    )
    result = run_compute_health(pass_dir=pass_dir)
    assert result["ok"] is True
    assert result["health"] == "waiting"
    assert result["idle"] is False
    assert result["tick_ok"] is True
    tick = pass_io.read_json(pass_io.tick_path(pass_dir))
    assert tick["health"] == "waiting"
    assert tick["ok"] is True
    assert tick["remaining"]["manual_open_ai_prs"] == 1
    assert tick["remaining"]["actionable_open_ai_prs"] == 0


def test_compute_health_ready_behind_actionable_pr_is_waiting_not_stall(tmp_path):
    """Late PR after survey_prs: catalog ready stays, but the repo is PR-first."""
    pass_dir = _pass(
        tmp_path,
        working={
            "prs_by_repo": {
                "a/one": [
                    {
                        "number": 313,
                        "head_ref": "ai/fix/27-x",
                        "labels": ["ai:generated"],
                    }
                ]
            },
            "ready_by_repo": {
                "a/one": [{"number": n, "title": f"r{n}"} for n in range(28, 33)]
            },
            "remaining_ready": 5,
            "remaining_prs": 1,
            "actionable_prs": 1,
            "manual_prs": 0,
            "actions": [{"step": "skip_ready_open_ai_pr", "repo": "a/one"}],
        },
    )
    result = run_compute_health(pass_dir=pass_dir)
    assert result["ok"] is True
    assert result["health"] == "waiting"
    assert result["tick_ok"] is True
    tick = pass_io.read_json(pass_io.tick_path(pass_dir))
    assert tick["health"] == "waiting"
    assert tick["ok"] is True
    assert tick["remaining"]["ready"] == 5
    assert tick["remaining"]["actionable_open_ai_prs"] == 1
    by_repo = {row["repo"]: row for row in tick["remaining"]["by_repo"]}
    assert by_repo["a/one"]["occupied"] is False
    assert by_repo["a/one"]["actionable_open_ai_prs"] == 1


def test_compute_health_ready_on_occupied_repo_is_waiting_not_stall(tmp_path):
    pass_dir = _pass(
        tmp_path,
        working={
            "ready_by_repo": {"a/one": [{"number": 29, "title": "next"}]},
            "remaining_ready": 1,
            "occupied_repos": ["a/one"],
            "live_issue_to_pr_repos": ["a/one"],
            "actions": [{"step": "skip_ready_repo_occupied", "repo": "a/one"}],
        },
    )
    result = run_compute_health(pass_dir=pass_dir)
    assert result["health"] == "waiting"
    tick = pass_io.read_json(pass_io.tick_path(pass_dir))
    assert tick["health"] == "waiting"
    assert tick["ok"] is True
    by_repo = {row["repo"]: row for row in tick["remaining"]["by_repo"]}
    assert by_repo["a/one"]["occupied"] is True


def test_compute_health_reports_probe_failed(tmp_path):
    pass_dir = _pass(
        tmp_path,
        working={
            "prs_by_repo": {},
            "ready_by_repo": {},
            "inbox_by_repo": {},
            "pr_survey_failed": ["a/one"],
            "inbox_survey_failed": [],
            "ready_survey_failed": [],
            "survey_errors": 1,
        },
    )
    result = run_compute_health(pass_dir=pass_dir)
    assert result["ok"] is True
    assert result["probe_failed"] is True
    assert result["health"] == "survey_error"
    source = Path(__file__).resolve().parents[1] / "src" / "lokay" / "proc" / "compute_health.py"
    assert "Health reports whether any survey probe remains failed." in source.read_text(
        encoding="utf-8"
    )
