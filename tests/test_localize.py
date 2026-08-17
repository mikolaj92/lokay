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


def test_long_localize_list_is_hint_not_cage():
    paths = [f"src/mod_{i}.py" for i in range(12)]
    text = issue_fix_prompt(_issue(), branch="ai/fix/88-x", paths=paths)
    assert "hints, not a cage" in text
    assert "Patch **only**" not in text


def test_polish_stop_and_acronym_do_not_pad_to_forty(tmp_path: Path):
    """Ticket prose is not an edit map. Weak hits must not fill the 40-slot cage."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "evidence.py").write_text("e\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_runtime_evidence.py").write_text("t\n", encoding="utf-8")
    planning = tmp_path / "planning" / "tasks"
    planning.mkdir(parents=True)
    (planning / "plan.md").write_text("# plan\n", encoding="utf-8")
    specs = tmp_path / "specs" / "api-boundary"
    specs.mkdir(parents=True)
    (specs / "plan.md").write_text("# spec\n", encoding="utf-8")
    for i in range(20):
        (planning / f"note-{i}.md").write_text("x\n", encoding="utf-8")

    seed = (
        "TK w salonie, orzeczeń w bazie nie ma\n\n"
        "Nie trzymać TK w salonie, gdy korpus jest pusty.\n"
        "Źródło luki: agent, bez patcha.\n"
    )
    loc = build_localization(
        worktree=tmp_path,
        seed_text=seed,
        extra_paths=(
            "src/evidence.py",
            "tests/test_runtime_evidence.py",
        ),
    )
    assert "src/evidence.py" in loc.paths
    assert "tests/test_runtime_evidence.py" in loc.paths
    assert len(loc.paths) < 40
    assert not any(p.endswith("plan.md") for p in loc.paths)
    assert "nie" not in {t.lower() for t in loc.matched_tokens}


def test_repo_package_name_is_not_a_forty_file_cage(tmp_path: Path):
    """influenzer#137: token = checkout name must not select the whole package."""
    pkg = tmp_path / "influenzer"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("\n", encoding="utf-8")
    (pkg / "brief_scan.py").write_text("\n", encoding="utf-8")
    (pkg / "brief_admit.py").write_text("\n", encoding="utf-8")
    for name in (
        "campaigns",
        "catalog",
        "cli",
        "config",
        "content",
        "domain",
        "effector",
        "envelope",
        "host",
        "playbook",
        "policy",
        "scheduler",
        "security",
        "storage",
        "tick",
    ):
        (pkg / f"{name}.py").write_text("x\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_e2e_gates.py").write_text("t\n", encoding="utf-8")

    seed = (
        "Used by tylko z faktu w briefie\n\n"
        "Repository: `mikolaj92/influenzer`\n"
        "Issue: #137 — Used by tylko z faktu w briefie\n\n"
        "„Used by” tylko z faktu w briefie/profilu. "
        "Nazwany klient, logo, case bez źródła = cisza.\n"
    )
    loc = build_localization(worktree=tmp_path, seed_text=seed)
    assert len(loc.paths) < 8
    assert "influenzer" not in loc.paths
    assert not any(
        p.startswith("influenzer/") and "brief" not in p for p in loc.paths
    )

    pinned = build_localization(
        worktree=tmp_path,
        seed_text=seed + "\nTouch `influenzer/brief_scan.py`.\n",
    )
    assert "influenzer/brief_scan.py" in pinned.paths
    assert len(pinned.paths) < 8


def test_inferred_scope_promotes_product_next_to_matching_tests(tmp_path: Path):
    """influenzer#26/#41: token hits must not cage the agent in tests/ only."""
    pkg = tmp_path / "influenzer"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("\n", encoding="utf-8")
    (pkg / "scan_due.py").write_text("def due():\n    return 1\n", encoding="utf-8")
    (pkg / "hom_draft.py").write_text("def draft():\n    return 1\n", encoding="utf-8")
    (pkg / "hom_verdict.py").write_text("def verdict():\n    return 1\n", encoding="utf-8")
    (pkg / "playbook.py").write_text("def play():\n    return 1\n", encoding="utf-8")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_scan_due.py").write_text(
        "from influenzer.scan_due import due\n", encoding="utf-8"
    )
    (tests / "test_hom_draft.py").write_text(
        "from influenzer.hom_draft import draft\n", encoding="utf-8"
    )
    (tests / "test_hom_verdict.py").write_text(
        "from influenzer.hom_verdict import verdict\n", encoding="utf-8"
    )
    (tests / "test_e2e_gates.py").write_text(
        "from influenzer.playbook import play\n", encoding="utf-8"
    )
    (tests / "test_brief_scan_cli.py").write_text("x\n", encoding="utf-8")
    (tests / "test_scan_path.py").write_text("x\n", encoding="utf-8")

    seed = (
        "Launch to jeden stos 24-48h, nie drugi kat spoleczny\n\n"
        "Repository: `mikolaj92/influenzer`\n"
        "Issue: #26 — Launch to jeden stos\n\n"
        "Jesli w oknie 48h jest juz noszalny draft github/hn (nawet po verdict pass), "
        "kolejny scan/score nie puszcza drugiego kata. Jedna historia, jeden stos.\n"
    )
    loc = build_localization(worktree=tmp_path, seed_text=seed)
    product = [p for p in loc.paths if p.startswith("influenzer/")]
    tests_hit = [p for p in loc.paths if p.startswith("tests/")]
    assert product, loc.paths
    assert "influenzer/scan_due.py" in loc.paths
    assert "influenzer/hom_draft.py" in loc.paths
    assert "influenzer/hom_verdict.py" in loc.paths
    assert "influenzer/playbook.py" not in loc.paths
    assert tests_hit
    assert loc.paths.index("influenzer/scan_due.py") < loc.paths.index(
        "tests/test_scan_due.py"
    )


def test_gate_only_test_hit_still_opens_imported_product(tmp_path: Path):
    """#41: token `gate` matched only tests/test_e2e_gates.py."""
    pkg = tmp_path / "influenzer"
    pkg.mkdir()
    (pkg / "hom.py").write_text("x\n", encoding="utf-8")
    (pkg / "domain.py").write_text("x\n", encoding="utf-8")
    (pkg / "unrelated.py").write_text("x\n", encoding="utf-8")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_e2e_gates.py").write_text(
        "from influenzer.hom import x\nfrom influenzer.domain import y\n",
        encoding="utf-8",
    )
    loc = build_localization(
        worktree=tmp_path,
        seed_text="Reply na X bez nowej mysli = cisza\n\ngate keeps the lane silent.\n",
    )
    assert "tests/test_e2e_gates.py" in loc.paths
    assert "influenzer/hom.py" in loc.paths
    assert "influenzer/domain.py" in loc.paths
    assert "influenzer/unrelated.py" not in loc.paths
