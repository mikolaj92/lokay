"""Hermetic tests for lokay-plan-issue + approach_plan."""

from __future__ import annotations

import json
from pathlib import Path

from lokay.approach_plan import (
    APPROACH_REL_PATH,
    approach_excerpt_from_diff,
    approach_present_in_diff,
    build_approach,
    render_approach_md,
    write_approach_file,
)
from lokay.models import Issue
from lokay.proc import plan_issue
from lokay.pr_review import review_prompt


def _issue(**kwargs) -> Issue:
    base = dict(
        repo="owner/repo",
        number=42,
        title="Add plan atom before run_agent",
        body=(
            "## Goal\n"
            "Write approach.md before the coding agent.\n\n"
            "## Ship\n"
            "- touch `src/lokay/proc/plan_issue.py`\n"
            "- update `fala/lokay.fala-package.toml`\n"
            "- add `tests/test_plan_issue.py`\n\n"
            "## Test plan\n"
            "- [ ] hermetic atom test\n"
            "- [ ] graph order plan before agent\n\n"
            "## Out of scope\n"
            "- merge/wait health fix\n"
            "- parallel agents\n"
        ),
        labels=["ai:ready"],
        assignees=["owner"],
        url="https://example.test/issues/42",
    )
    base.update(kwargs)
    return Issue(**base)


def test_build_approach_extracts_sections_and_paths():
    plan = build_approach(_issue())
    assert plan.source == "deterministic"
    assert "approach.md" in plan.goal.lower() or "Write approach" in plan.goal
    assert "src/lokay/proc/plan_issue.py" in plan.files_likely
    assert "fala/lokay.fala-package.toml" in plan.files_likely
    assert any("hermetic" in t.lower() for t in plan.test_plan)
    assert any("merge" in n.lower() or "parallel" in n.lower() for n in plan.non_goals)
    assert any(
        "collector boundary" in note.lower()
        and "background" in note.lower()
        and "must not populate data" in note.lower()
        for note in plan.notes
    )


def test_render_and_write_approach_file(tmp_path: Path):
    plan = build_approach(_issue())
    content = render_approach_md(plan)
    assert "# Approach plan" in content
    assert "lokay-approach" in content
    path = write_approach_file(tmp_path, content)
    assert path == tmp_path / APPROACH_REL_PATH
    assert path.is_file()
    assert "Non-goals" in path.read_text(encoding="utf-8")


def test_plan_issue_cli_planned_no_write(tmp_path: Path, capsys):
    wt = tmp_path / "wt"
    wt.mkdir()
    code = plan_issue.main(
        [
            "--worktree",
            str(wt),
            "--repo",
            "owner/repo",
            "--issue",
            "7",
            "--title",
            "Tiny fix",
            "--body",
            "## Goal\nFix the thing in `src/lokay/x.py`\n",
        ]
    )
    assert code == 0
    out = json.loads(capsys.readouterr().out.strip())
    assert out["ok"] is True
    assert out["planned"] is True
    assert out["wrote"] is False
    assert not (wt / APPROACH_REL_PATH).exists()
    assert "Approach plan" in out["content"]


def test_plan_issue_cli_live_writes(tmp_path: Path, monkeypatch, capsys):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        f"""
mode: dry-run
github:
  assignee: t
  ready_label: ai:ready
  blocked_label: ai:blocked
  branch_prefix: ai/fix
  pr_labels: [ai:generated]
repos:
  - name: owner/repo
    clone_path: {tmp_path / "clone"}
executor:
  enabled: false
  agent: grok
merge:
  enabled: false
worktrees:
  root: {tmp_path / "wts"}
state:
  path: {tmp_path / "state.jsonl"}
""",
        encoding="utf-8",
    )
    wt = tmp_path / "wt"
    wt.mkdir()
    monkeypatch.setattr(plan_issue, "mutations_allowed", lambda **k: True)
    issue_json = tmp_path / "issue.json"
    issue_json.write_text(json.dumps(_issue().to_dict()), encoding="utf-8")
    code = plan_issue.main(
        [
            "--config",
            str(cfg),
            "--live",
            "--worktree",
            str(wt),
            "--issue-json",
            str(issue_json),
        ]
    )
    assert code == 0
    out = json.loads(capsys.readouterr().out.strip())
    assert out["ok"] is True
    assert out["wrote"] is True
    assert (wt / APPROACH_REL_PATH).is_file()
    assert "plan_issue.py" in (wt / APPROACH_REL_PATH).read_text(encoding="utf-8")


def test_plan_issue_llm_flag_fail_closed(capsys):
    code = plan_issue.main(
        [
            "--worktree",
            "/tmp",
            "--repo",
            "owner/repo",
            "--issue",
            "1",
            "--llm",
        ]
    )
    assert code == 1
    out = json.loads(capsys.readouterr().out.strip())
    assert out["ok"] is False
    assert out.get("llm_requested") is True


def test_approach_present_in_diff_soft_signal():
    diff = """
diff --git a/.lokay/approach.md b/.lokay/approach.md
new file mode 100644
--- /dev/null
+++ b/.lokay/approach.md
@@ -0,0 +1,3 @@
+# Approach plan
+
+## Goal
+Ship the plan atom
"""
    assert approach_present_in_diff(diff) is True
    excerpt = approach_excerpt_from_diff(diff)
    assert "Approach plan" in excerpt
    assert approach_present_in_diff("diff --git a/src/x.py b/src/x.py\n") is False


def test_review_prompt_notes_missing_approach_as_soft():
    text = review_prompt(
        repo="owner/repo",
        pr_number=9,
        title="x",
        body="y",
        head_ref="ai/fix/9-x",
        diff_text="diff --git a/src/a.py b/src/a.py\n",
        checks_text="",
    )
    assert "soft nit" in text.lower() or "soft signal" in text.lower()
    assert "not a human gate" in text.lower() or "never needs_human" in text.lower()
    assert "Approach plan" in text or "approach.md" in text
    assert "Collector boundary" in text
    assert "must not use Pi or the mill to populate data" in text


def test_review_prompt_notes_present_approach():
    diff = (
        "diff --git a/.lokay/approach.md b/.lokay/approach.md\n"
        "--- /dev/null\n+++ b/.lokay/approach.md\n"
        "@@ -0,0 +1,2 @@\n+# Approach plan\n+## Goal\n"
    )
    text = review_prompt(
        repo="owner/repo",
        pr_number=9,
        title="x",
        body="y",
        head_ref="ai/fix/9-x",
        diff_text=diff,
        checks_text="",
    )
    assert "appears in this PR diff" in text


def test_commit_all_force_adds_approach_md(tmp_path: Path, monkeypatch):
    """Approach evidence must stage even when `.lokay/` is gitignored."""
    from lokay import git_commit

    wt = tmp_path / "wt"
    approach = wt / ".lokay" / "approach.md"
    approach.parent.mkdir(parents=True)
    approach.write_text("# Approach plan\n", encoding="utf-8")
    seen: list[list[str]] = []

    class FakeRunner:
        def run_checked(self, spec, *, live):
            seen.append(list(spec.argv))
            return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        def run(self, spec, *, live):
            # cached-diff --quiet → nonzero means dirty index (something to commit).
            if tuple(spec.argv[:3]) == ("git", "diff", "--cached"):
                return type("R", (), {"returncode": 1, "stdout": "", "stderr": ""})()
            return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    did = git_commit.commit_all(FakeRunner(), wt, "msg", live=True)
    assert did is True
    assert ["git", "add", "-A"] in seen
    assert ["git", "add", "-f", "--", ".lokay/approach.md"] in seen
    assert any(a[:2] == ["git", "commit"] for a in seen)


def test_commit_all_force_adds_localize_json(tmp_path: Path):
    """Localization evidence must stage even when `.lokay/` is gitignored."""
    from lokay import git_commit

    wt = tmp_path / "wt"
    loc = wt / ".lokay" / "localize.json"
    loc.parent.mkdir(parents=True)
    loc.write_text('{"paths":["src/x.py"]}\n', encoding="utf-8")
    seen: list[list[str]] = []

    class FakeRunner:
        def run_checked(self, spec, *, live):
            seen.append(list(spec.argv))
            return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        def run(self, spec, *, live):
            if tuple(spec.argv[:3]) == ("git", "diff", "--cached"):
                return type("R", (), {"returncode": 1, "stdout": "", "stderr": ""})()
            return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    did = git_commit.commit_all(FakeRunner(), wt, "msg", live=True)
    assert did is True
    assert ["git", "add", "-f", "--", ".lokay/localize.json"] in seen
