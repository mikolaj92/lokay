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
from lokay.pr_review import review_prompt
from lokay.proc import plan_issue
from lokay.proc.validate_plan import validate_plan


def test_plan_contract_accepts_a_complete_plan_and_rejects_the_rest():
    good = {
        "ok": True,
        "goal": "add the atom",
        "files": ["src/lokay/proc/plan_issue.py"],
        "test_command": "pytest -q",
        "non_goals": ["merge"],
        "stop_if": ["auth"],
    }
    assert validate_plan(json.dumps(good))["ok"] is True

    for bad in (
        {"ok": False, "reason": "underspecified"},
        {"ok": False, "reason": "too_large"},
        {"ok": False, "reason": "dangerous"},
    ):
        out = validate_plan(json.dumps(bad))
        assert out["ok"] is False and out["reason"] == bad["reason"]

    for raw in ('{"ok": true}', '{"ok": false, "reason": "bored"}', "not json"):
        assert validate_plan(raw)["ok"] is False


def test_a_built_plan_must_carry_a_goal_and_files():
    """The deterministic planner's own dict passes the same contract."""
    assert validate_plan({"goal": "add the atom", "files_likely": ["src/a.py"]})["ok"]
    assert validate_plan({"goal": "", "files_likely": ["src/a.py"]})["reason"] == "plan_incomplete"
    assert validate_plan({"goal": "add", "files_likely": []})["reason"] == "plan_incomplete"


def test_building_a_plan_with_no_files_fails_closed(tmp_path: Path):
    """An issue that names no file does not become a plan."""
    from lokay.proc.build_issue_approach import build

    out = build({"worktree": str(tmp_path), "rel_path": ".lokay/approach.md",
                 "issue": {"repo": "o/r", "number": 1, "title": "Do a thing", "body": ""}})
    assert out["ok"] is False and out["reason"] == "plan_incomplete"


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


def test_plan_issue_planned_record_does_not_write():
    from lokay.proc.record_issue_approach_write import record

    assert record({"route": "planned"}, {})["route"] == "planned"


def test_incomplete_plan_routes_to_terminal_before_a_live_write(tmp_path: Path):
    """A rejected plan never authorizes the approach file, even live."""
    from lokay.proc.authorize_issue_plan_write import authorize
    from lokay.proc.issue_plan_terminal import terminal
    from lokay.proc.record_issue_approach_write import record

    request = {"worktree": str(tmp_path), "rel_path": ".lokay/approach.md",
               "issue": {"repo": "o/r", "number": 35}}
    approach = {"ok": False, "reason": "plan_incomplete", "plan": {"files_likely": []}}
    authorized = authorize(request, approach, config_path=None, live=True)
    assert authorized["route"] == "terminal"
    assert authorized["reason"] == "plan_incomplete"
    assert not (tmp_path / ".lokay" / "approach.md").exists()
    recorded = record(authorized, {})
    result = terminal(request, approach, authorized, recorded)["result"]
    assert result["ok"] is False and result["reason"] == "plan_incomplete"
    assert result["wrote"] is False and "content" not in str(result.get("error"))


def test_issue_plan_terminal_reports_written():
    from lokay.proc.issue_plan_terminal import terminal

    out = terminal(
        {
            "issue": {"repo": "a/b", "number": 7},
            "worktree": "/w",
            "rel_path": ".lokay/approach.md",
        },
        {
            "source": "deterministic",
            "content": "# Approach",
            "plan": {},
            "approach_path": "/w/.lokay/approach.md",
        },
        {"route": "write"},
        {"route": "written"},
    )["result"]
    assert out["ok"] is True and out["wrote"] is True and out["planned"] is False


def test_plan_issue_cli_rejects_fake_llm_slot(capsys):
    code = plan_issue.main(
        ["--worktree", "/tmp", "--repo", "a/b", "--issue", "1", "--llm"]
    )
    out = json.loads(capsys.readouterr().out.strip())
    assert code == 1 and out["llm_requested"] is True


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


def test_plan_cites_feature_map_only_when_the_tree_has_one(tmp_path: Path):
    bare = build_approach(_issue(), worktree=tmp_path)
    assert all("feature-map" not in note for note in bare.notes)
    memory = tmp_path / ".lokay" / "memory"
    memory.mkdir(parents=True)
    (memory / "feature-map.md").write_text("door opens from the hall\n", encoding="utf-8")
    cited = build_approach(_issue(), worktree=tmp_path)
    rendered = render_approach_md(cited)
    assert any("door opens from the hall" in note for note in cited.notes)
    assert ".lokay/memory/feature-map.md" in rendered


def test_one_declared_kind_loads_only_that_playbook(tmp_path: Path):
    from lokay.proc.classify_ticket_kind import classify

    skills = tmp_path / ".lokay" / "skills"
    skills.mkdir(parents=True)
    (skills / "bug.md").write_text("reproduce first\n", encoding="utf-8")
    (skills / "feat.md").write_text("name the user path\n", encoding="utf-8")
    issue = _issue(body="Kind: bug\n\n" + _issue().body, labels=["kind:feat", "ai:ready"])
    assert classify(issue) == "bug"
    plan = build_approach(issue, worktree=tmp_path)
    rendered = render_approach_md(plan)
    assert plan.kind == "bug"
    assert "reproduce first" in rendered
    assert "name the user path" not in rendered


def test_missing_kind_loads_no_playbook(tmp_path: Path):
    from lokay.proc.classify_ticket_kind import classify

    skills = tmp_path / ".lokay" / "skills"
    skills.mkdir(parents=True)
    (skills / "bug.md").write_text("reproduce first\n", encoding="utf-8")
    issue = _issue()
    assert classify(issue) == ""
    plan = build_approach(issue, worktree=tmp_path)
    assert plan.kind == ""
    assert "reproduce first" not in render_approach_md(plan)


def test_unknown_kind_fails_closed(tmp_path: Path):
    from lokay.proc.classify_ticket_kind import classify

    assert classify(_issue(body="Kind: essay\n\nfix it")) == ""
    assert classify(_issue(labels=["kind:bug", "kind:feat"])) == ""


def test_garden_is_one_kind_and_loads_only_its_playbook(tmp_path: Path):
    from lokay.proc.classify_ticket_kind import classify

    skills = tmp_path / ".lokay" / "skills"
    skills.mkdir(parents=True)
    (skills / "garden.md").write_text("one small debt, then stop\n", encoding="utf-8")
    (skills / "chore.md").write_text("sweep the repo\n", encoding="utf-8")
    issue = _issue(labels=["kind:garden"])
    assert classify(issue) == "garden"
    plan = build_approach(issue, worktree=tmp_path)
    rendered = render_approach_md(plan)
    assert plan.kind == "garden"
    assert "one small debt, then stop" in rendered
    assert "sweep the repo" not in rendered


def test_review_prompt_keeps_memory_and_strips_only_the_plan():
    diff = (
        "diff --git a/.lokay/approach.md b/.lokay/approach.md\n"
        "--- /dev/null\n+++ b/.lokay/approach.md\n"
        "@@ -0,0 +1,2 @@\n+# Approach plan\n+SECRET_PLAN_GOAL\n"
        "diff --git a/.lokay/memory/feature-map.md b/.lokay/memory/feature-map.md\n"
        "--- /dev/null\n+++ b/.lokay/memory/feature-map.md\n"
        "@@ -0,0 +1 @@\n+FEATURE_MAP_EVIDENCE\n"
        "diff --git a/.lokay/memory/paved-path.md b/.lokay/memory/paved-path.md\n"
        "--- /dev/null\n+++ b/.lokay/memory/paved-path.md\n"
        "@@ -0,0 +1 @@\n+PAVED_PATH_EVIDENCE\n"
        "diff --git a/.lokay/lessons/latch.md b/.lokay/lessons/latch.md\n"
        "--- /dev/null\n+++ b/.lokay/lessons/latch.md\n"
        "@@ -0,0 +1 @@\n+LESSON_EVIDENCE\n"
        "diff --git a/verify-receipt.json b/verify-receipt.json\n"
        "--- /dev/null\n+++ b/verify-receipt.json\n"
        "@@ -0,0 +1 @@\n+VERIFY_RECEIPT\n"
    )
    text = review_prompt(
        repo="owner/repo", pr_number=9, title="x", body="y",
        head_ref="ai/fix/9-x", diff_text=diff, checks_text="",
    )
    assert "SECRET_PLAN_GOAL" not in text
    assert "FEATURE_MAP_EVIDENCE" in text
    assert "PAVED_PATH_EVIDENCE" in text
    assert "LESSON_EVIDENCE" in text
    assert "VERIFY_RECEIPT" in text


def test_review_prompt_stays_blind_when_approach_missing():
    text = review_prompt(
        repo="owner/repo",
        pr_number=9,
        title="x",
        body="y",
        head_ref="ai/fix/9-x",
        diff_text="diff --git a/src/a.py b/src/a.py\n",
        checks_text="",
    )
    lowered = text.lower()
    assert "Collector boundary" in text
    assert "must not use Pi or the lokay to populate data" in text
    assert "approach.md" not in lowered
    assert "soft signal" not in lowered
    assert "compare the" not in lowered


def test_review_prompt_strips_approach_hunk_from_diff():
    diff = (
        "diff --git a/.lokay/approach.md b/.lokay/approach.md\n"
        "--- /dev/null\n+++ b/.lokay/approach.md\n"
        "@@ -0,0 +1,2 @@\n+# Approach plan\n+## Goal\n"
        "diff --git a/src/a.py b/src/a.py\n"
        "--- a/src/a.py\n+++ b/src/a.py\n"
        "@@ -1 +1,2 @@\n keep\n+CODE_ONLY\n"
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
    assert "CODE_ONLY" in text
    assert "Approach plan" not in text
    assert "approach.md" not in text.lower()


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
    assert any("commit" in a for a in seen)


def test_commit_all_uses_localize_paths_instead_of_evidence(tmp_path: Path):
    """A localization file switches commit_all from add-all to scoped paths."""
    from lokay import git_commit

    wt = tmp_path / "wt"
    loc = wt / ".lokay" / "localize.json"
    loc.parent.mkdir(parents=True)
    loc.write_text('{"paths":["src/x.py"]}\n', encoding="utf-8")
    source = wt / "src" / "x.py"
    source.parent.mkdir()
    source.write_text("changed\n", encoding="utf-8")
    seen: list[list[str]] = []

    class FakeRunner:
        def run_checked(self, spec, *, live):
            seen.append(list(spec.argv))
            stdout = "src/x.py\0" if spec.argv[:2] == ("git", "ls-files") else ""
            return type("R", (), {"returncode": 0, "stdout": stdout, "stderr": ""})()

        def run(self, spec, *, live):
            if spec.argv[:2] == ("git", "ls-files"):
                return type("R", (), {"returncode": 0, "stdout": "src/x.py\0", "stderr": ""})()
            if tuple(spec.argv[:3]) == ("git", "diff", "--cached"):
                return type("R", (), {"returncode": 1, "stdout": "", "stderr": ""})()
            return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    did = git_commit.commit_all(FakeRunner(), wt, "msg", live=True)
    assert did is True
    assert ["git", "add", "-A"] not in seen
    assert ["git", "add", "-f", "--", ".lokay/localize.json"] not in seen
    assert ["git", "add", "-A", "--", ":(literal)src/x.py"] in seen
    assert any("commit" in a and "--only" in a for a in seen)
