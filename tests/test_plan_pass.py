from pathlib import Path

from lokay.passkit import io as pass_io
from lokay.proc.plan_pass import run_plan_pass


def test_plan_pass_skips_blocked_inbox_issue_without_spending_triage_budget(
    tmp_path: Path,
):
    pass_dir = tmp_path / "pass"
    pass_dir.mkdir()
    stuck_path = tmp_path / "stuck.json"
    stuck_path.write_text(
        '{"issues": {"owner/repo#1": {"blocked": true}}}\n',
        encoding="utf-8",
    )
    pass_io.write_json(
        pass_io.begin_path(pass_dir),
        {
            "live": True,
            "repos": ["owner/repo"],
            "triage_budget": 1,
            "stuck_path": str(stuck_path),
        },
    )
    pass_io.write_json(
        pass_io.survey_path(pass_dir),
        {
            "inbox_issues_by_repo": {
                "owner/repo": [{"number": 1}, {"number": 2}],
            },
            "prs_by_repo": {"owner/repo": []},
            "ready_by_repo": {"owner/repo": []},
            "pr_survey_failed": [],
        },
    )
    pass_io.write_json(pass_io.working_path(pass_dir), {"actions": []})

    result = run_plan_pass(pass_dir=str(pass_dir))

    assert result["ok"] is True
    plan = pass_io.read_json(pass_io.plan_path(pass_dir))
    assert plan["triage_targets"] == [{"repo": "owner/repo", "issue": 2}]
    assert plan["triage_budget_remaining"] == 0
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    assert any(
        action.get("step") == "skip_inbox_triage_stuck_blocked"
        and action.get("repo") == "owner/repo"
        and action.get("issue") == 1
        for action in working["actions"]
    )
