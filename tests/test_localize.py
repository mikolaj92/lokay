"""Hermetic tests for lokay-localize (Agentless path list before run_agent)."""

from __future__ import annotations

import json
from pathlib import Path

from lokay.graph_run import describe_package
from lokay.localize import (
    LOCALIZE_REL_PATH,
    build_localization,
    select_paths,
    walk_repo_tree,
    write_localize_file,
)
from lokay.models import Issue
from lokay.proc import localize
from lokay.prompts import issue_fix_prompt, repair_pr_prompt


def _issue(**kwargs) -> Issue:
    base = dict(
        repo="owner/repo",
        number=88,
        title="Atom localize before run_agent",
        body=(
            "## Skutek\n"
            "Before run_agent Fala calls atom `localize`.\n\n"
            "Touch `src/lokay/proc/localize.py` and `fala/lokay.fala-package.toml`.\n"
            "Add `tests/test_localize.py`.\n"
        ),
        labels=["ai:ready"],
        assignees=["owner"],
        url="https://example.test/issues/88",
    )
    base.update(kwargs)
    return Issue(**base)


def test_walk_and_select_prefers_explicit_seed_paths(tmp_path: Path):
    (tmp_path / "src" / "lokay" / "proc").mkdir(parents=True)
    (tmp_path / "src" / "lokay" / "proc" / "localize.py").write_text("x\n", encoding="utf-8")
    (tmp_path / "src" / "lokay" / "other.py").write_text("y\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_localize.py").write_text("z\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("hi\n", encoding="utf-8")

    tree = walk_repo_tree(tmp_path)
    assert "src/lokay/proc/localize.py" in tree
    paths, seed, _matched = select_paths(
        tree=tree,
        seed_text="edit `src/lokay/proc/localize.py` and tests/test_localize.py",
    )
    assert "src/lokay/proc/localize.py" in paths
    assert "tests/test_localize.py" in seed or "tests/test_localize.py" in paths


def test_build_localization_fail_closed_empty_noise():
    loc = build_localization(
        worktree=None,
        seed_text="the and for with that this",
    )
    assert loc.paths == ()


def test_build_localization_from_issue_and_tree(tmp_path: Path):
    (tmp_path / "src" / "lokay" / "proc").mkdir(parents=True)
    target = tmp_path / "src" / "lokay" / "proc" / "localize.py"
    target.write_text("# atom\n", encoding="utf-8")
    (tmp_path / "fala").mkdir()
    (tmp_path / "fala" / "lokay.fala-package.toml").write_text("id='x'\n", encoding="utf-8")

    issue = _issue()
    seed = f"{issue.title}\n{issue.body}"
    loc = build_localization(worktree=tmp_path, seed_text=seed)
    assert loc.paths
    assert any("localize" in p for p in loc.paths)
    path = write_localize_file(tmp_path, loc)
    assert path == tmp_path / LOCALIZE_REL_PATH
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["paths"]


def test_localize_cli_planned_no_write(tmp_path: Path, capsys):
    wt = tmp_path / "wt"
    (wt / "src" / "lokay").mkdir(parents=True)
    (wt / "src" / "lokay" / "x.py").write_text("1\n", encoding="utf-8")
    code = localize.main(
        [
            "--worktree",
            str(wt),
            "--repo",
            "owner/repo",
            "--issue",
            "88",
            "--title",
            "Fix x",
            "--body",
            "Change `src/lokay/x.py` only.\n",
        ]
    )
    assert code == 0
    out = json.loads(capsys.readouterr().out.strip())
    assert out["ok"] is True
    assert out["planned"] is True
    assert out["wrote"] is False
    assert "src/lokay/x.py" in out["paths"]
    assert not (wt / LOCALIZE_REL_PATH).exists()


def test_localize_cli_live_writes(tmp_path: Path, monkeypatch, capsys):
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
    (wt / "src").mkdir(parents=True)
    (wt / "src" / "a.py").write_text("a\n", encoding="utf-8")
    monkeypatch.setattr(localize, "mutations_allowed", lambda **k: True)
    issue_json = tmp_path / "issue.json"
    issue_json.write_text(
        json.dumps(
            _issue(
                body="Patch `src/a.py` for the bug.\n",
                title="patch a",
            ).to_dict()
        ),
        encoding="utf-8",
    )
    code = localize.main(
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
    assert (wt / LOCALIZE_REL_PATH).is_file()
    assert "src/a.py" in out["paths"]


def test_localize_cli_empty_seed_fails(tmp_path: Path, capsys):
    wt = tmp_path / "wt"
    wt.mkdir()
    code = localize.main(["--worktree", str(wt)])
    assert code == 1
    out = json.loads(capsys.readouterr().out.strip())
    assert out["ok"] is False
    assert out.get("reason") == "empty_seed"


def test_localize_cli_empty_paths_fails(tmp_path: Path, capsys):
    wt = tmp_path / "wt"
    wt.mkdir()
    code = localize.main(
        [
            "--worktree",
            str(wt),
            "--seed",
            "the and for with that this are was been",
        ]
    )
    assert code == 1
    out = json.loads(capsys.readouterr().out.strip())
    assert out["ok"] is False
    assert out.get("reason") == "empty_paths"


def test_issue_to_pr_localize_before_run_agent():
    desc = describe_package()
    path = next(p for p in desc["paths"] if p["id"] == "issue_to_pr")
    by_id = {n["id"]: n for n in path["nodes"]}
    assert "localize" in by_id
    assert "localize" in by_id["run_agent"]["conduction"]
    assert "plan_issue" in by_id["localize"]["conduction"]
    assert "run_agent" not in by_id["localize"]["conduction"]


def test_pr_repair_localize_before_run_agent():
    desc = describe_package()
    path = next(p for p in desc["paths"] if p["id"] == "pr_repair")
    by_id = {n["id"]: n for n in path["nodes"]}
    assert "localize" in by_id
    assert "localize" in by_id["run_agent"]["conduction"]
    assert "worktree_add" in by_id["localize"]["conduction"]


def test_issue_fix_prompt_includes_edit_scope():
    text = issue_fix_prompt(
        _issue(),
        branch="ai/fix/88-x",
        paths=["src/lokay/proc/localize.py", "tests/test_localize.py"],
    )
    assert "Edit scope" in text
    assert "src/lokay/proc/localize.py" in text
    assert "localize.json" in text


def test_repair_prompt_includes_edit_scope():
    text = repair_pr_prompt(
        repo="owner/repo",
        pr_number=3,
        branch="ai/fix/3-x",
        checks_text="FAILED tests/test_x.py",
        paths=["tests/test_x.py"],
    )
    assert "Edit scope" in text
    assert "tests/test_x.py" in text
