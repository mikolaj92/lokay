"""Factory coding harness must not inherit product take_issue/gh playbooks."""

from lokay.agent import FACTORY_WORKFLOW_BOUNDARY, with_coding_boundaries
from lokay.models import Issue
from lokay.prompts import issue_fix_prompt, local_test_repair_prompt, timeout_resume_prompt


def test_factory_workflow_boundary_bans_take_and_gh():
    assert "take_issue" in FACTORY_WORKFLOW_BOUNDARY
    assert "`gh`" in FACTORY_WORKFLOW_BOUNDARY or "call `gh`" in FACTORY_WORKFLOW_BOUNDARY
    assert "AGENTS.md" in FACTORY_WORKFLOW_BOUNDARY
    wrapped = with_coding_boundaries("Implement the fix.")
    assert FACTORY_WORKFLOW_BOUNDARY in wrapped


def test_issue_fix_prompt_supersedes_product_publication_playbooks():
    issue = Issue(
        repo="mikolaj92/Temida",
        number=5682,
        title="x",
        body="run take_issue",
        url="https://github.com/mikolaj92/Temida/issues/5682",
        labels=[],
        assignees=[],
    )
    text = issue_fix_prompt(issue, branch="ai/fix/5682-x")
    assert "take_issue" in text
    assert "AGENTS.md" in text
    assert "Do NOT merge" in text or "do NOT" in text.lower() or "Do NOT" in text


def test_repair_and_resume_prompts_ban_product_gh_path():
    repair = local_test_repair_prompt(repo="a/b", branch="x", log_text="FAIL")
    resume = timeout_resume_prompt(repo="a/b", branch="x", timeout_seconds=10)
    assert "take_issue" in repair and "AGENTS.md" in repair
    assert "take_issue" in resume and "AGENTS.md" in resume


def test_issue_fix_prompt_inlines_body_without_github_url():
    issue = Issue(
        repo="mikolaj92/Temida",
        number=5682,
        title="fix hermes",
        body="full body text here",
        url="https://github.com/mikolaj92/Temida/issues/5682",
        labels=[],
        assignees=[],
    )
    text = issue_fix_prompt(issue, branch="ai/fix/5682-x")
    assert "full body text here" in text
    assert "Issue URL:" not in text
    assert "https://github.com/mikolaj92/Temida/issues/5682" not in text
