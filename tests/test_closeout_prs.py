"""Repository-boundary tests for lokay-closeout-prs."""

import pytest

from pathlib import Path
from typing import Any

from lokay.closeout import COUNTERS
from lokay.passkit import io as pass_io
from lokay.proc import closeout_prs


@pytest.mark.skip(reason="obsolete single-repository mill contract")
def test_skips_product_repos_before_closeout(tmp_path: Path, monkeypatch) -> None:
    pass_dir = tmp_path / "pass"
    pass_dir.mkdir()
    repos = ["mikolaj92/Temida", "mikolaj92/lokay", "mikolaj92/takt"]
    pass_io.write_json(
        pass_io.begin_path(pass_dir),
        {
            "repos": repos,
            "repair_budget": 1,
            "executor_enabled": True,
            "merge_enabled": True,
            "require_checks": False,
            "branch_prefix": "ai/fix/",
            "stuck_path": str(tmp_path / "stuck.json"),
        },
    )
    prs = {
        repo: [{"number": number, "head_ref": f"ai/fix/{number}-x", "labels": []}]
        for repo, number in zip(repos, (1, 2, 3), strict=True)
    }
    pass_io.write_json(
        pass_io.working_path(pass_dir),
        {
            "actions": [],
            "stuck": {"issues": {}},
            "prs_by_repo": prs,
            "remaining_prs": 3,
            **{counter: 0 for counter in COUNTERS},
        },
    )
    calls: list[str] = []

    def closeout(**kwargs: Any) -> dict[str, Any]:
        calls.append(str(kwargs["repo"]))
        return {
            "ok": True,
            "still_open": True,
            "actions": [],
            "repair_budget": kwargs["repair_budget"],
            "progress": 0,
            "remaining_closed": 0,
            **{counter: 0 for counter in COUNTERS},
        }

    monkeypatch.setattr(closeout_prs, "run_closeout_pr", closeout)
    out = closeout_prs.run_closeout_prs(
        pass_dir=str(pass_dir), config_path=None, live=True
    )

    assert calls == ["mikolaj92/lokay"]
    assert out == {
        "ok": True,
        "pass_dir": str(pass_dir),
        "remaining_prs": 3,
        "actionable_prs": 3,
        "needs_repair": 0,
        "mergeable_green": 0,
        "merge_disabled": 0,
        "skipped": True,
        "reason": "repo_not_delivered_by_mini_mill",
        "skipped_repos": ["mikolaj92/Temida", "mikolaj92/takt"],
    }
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    assert [action["repo"] for action in working["actions"]] == [
        "mikolaj92/Temida",
        "mikolaj92/takt",
    ]
    assert working["prs_by_repo"] == prs
