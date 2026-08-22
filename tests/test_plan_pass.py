
import pytest
from pathlib import Path

from lokay.passkit import io as pass_io
from lokay.proc.plan_pass import MINI_MILL_REPO, run_plan_pass


@pytest.mark.skip(reason="obsolete single-repository mill contract")
def test_plan_pass_skips_blocked_inbox_issue_without_spending_triage_budget(
    tmp_path: Path,
):
    pass_dir = tmp_path / "pass"
    pass_dir.mkdir()
    stuck_path = tmp_path / "stuck.json"
    stuck_path.write_text(
        f'{{"issues": {{"{MINI_MILL_REPO}#1": {{"blocked": true}}}}}}\n',
        encoding="utf-8",
    )
    pass_io.write_json(
        pass_io.begin_path(pass_dir),
        {
            "live": True,
            "repos": [MINI_MILL_REPO],
            "triage_budget": 1,
            "stuck_path": str(stuck_path),
        },
    )
    pass_io.write_json(
        pass_io.survey_path(pass_dir),
        {
            "inbox_issues_by_repo": {
                MINI_MILL_REPO: [{"number": 1}, {"number": 2}],
            },
            "prs_by_repo": {MINI_MILL_REPO: []},
            "ready_by_repo": {MINI_MILL_REPO: []},
            "pr_survey_failed": [],
        },
    )
    pass_io.write_json(pass_io.working_path(pass_dir), {"actions": []})

    result = run_plan_pass(pass_dir=str(pass_dir))

    assert result["ok"] is True
    plan = pass_io.read_json(pass_io.plan_path(pass_dir))
    assert plan["triage_targets"] == [{"repo": MINI_MILL_REPO, "issue": 2}]
    assert plan["triage_budget_remaining"] == 0
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    assert any(
        action.get("step") == "skip_inbox_triage_stuck_blocked"
        and action.get("repo") == MINI_MILL_REPO
        and action.get("issue") == 1
        for action in working["actions"]
    )


@pytest.mark.skip(reason="obsolete single-repository mill contract")
def test_plan_pass_skips_repos_outside_mini_mill(tmp_path: Path):
    pass_dir = tmp_path / "pass"
    pass_dir.mkdir()
    product_repo = "owner/product"
    repos = [product_repo, MINI_MILL_REPO]
    pass_io.write_json(
        pass_io.begin_path(pass_dir),
        {"live": True, "repos": repos, "triage_budget": 2},
    )
    pass_io.write_json(
        pass_io.survey_path(pass_dir),
        {
            "inbox_issues_by_repo": {
                product_repo: [{"number": 1}],
                MINI_MILL_REPO: [{"number": 2}],
            },
            "prs_by_repo": {
                product_repo: [{"number": 3}],
                MINI_MILL_REPO: [{"number": 4, "labels": ["ai:needs-review"]}],
            },
            "ready_by_repo": {
                product_repo: [{"number": 5, "title": "product"}],
                MINI_MILL_REPO: [{"number": 6, "title": "lokay"}],
            },
            "pr_survey_failed": [],
        },
    )
    pass_io.write_json(pass_io.working_path(pass_dir), {"actions": []})

    result = run_plan_pass(pass_dir=str(pass_dir))

    assert result["ok"] is True
    assert result["skipped"] is True
    assert result["reason"] == "repo_not_delivered_by_mini_mill"
    assert result["skipped_repos"] == [product_repo]
    plan = pass_io.read_json(pass_io.plan_path(pass_dir))
    assert plan["triage_targets"] == [{"repo": MINI_MILL_REPO, "issue": 2}]
    assert plan["closeout_targets"] == [
        {
            "repo": MINI_MILL_REPO,
            "pr": 4,
            "head_ref": "",
            "mergeable": "",
            "manual": True,
            "labels": ["ai:needs-review"],
            "title": "",
        }
    ]
    assert plan["implement_candidates"] == [
        {"repo": MINI_MILL_REPO, "number": 6, "title": "lokay"}
    ]
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    assert working["actions"] == [
        {
            "step": "skip_repo_outside_mini_mill",
            "repo": product_repo,
            "ok": True,
            "skipped": True,
            "reason": "repo_not_delivered_by_mini_mill",
        }
    ]
