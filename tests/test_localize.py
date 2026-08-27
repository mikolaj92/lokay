"""Hermetic tests for lokay-localize (Agentless path list before run_agent)."""

from __future__ import annotations


import json
from pathlib import Path

from lokay.graph_run import describe_package
from lokay.localize import (
    LOCALIZE_REL_PATH,
    build_localization,
    extract_seed_paths,
    load_existing_localize_paths,
    localize_belongs_to_issue,
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
    (tmp_path / "src" / "lokay" / "proc" / "localize.py").write_text(
        "x\n", encoding="utf-8"
    )
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


def test_structured_change_section_excludes_problem_counterexample(tmp_path: Path):
    factory_begin = "src/lokay/proc/factory_begin.py"
    commit_all = "src/lokay/proc/commit_all.py"
    for rel in (factory_begin, commit_all):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# product\n", encoding="utf-8")

    body = (
        "## Dziura\n"
        f"Counterexample touched `{factory_begin}` and 291/303/321.\n\n"
        "## Zmiana\n"
        f"Change `{commit_all}` only.\n\n"
        "## Test\n"
        f"Assert `{factory_begin}` is absent.\n"
    )

    seed_paths = extract_seed_paths(body)
    assert commit_all in seed_paths
    assert factory_begin not in seed_paths
    loc = build_localization(worktree=tmp_path, seed_text=body)
    assert commit_all in loc.seed_paths
    assert commit_all in loc.paths
    assert factory_begin not in loc.seed_paths
    assert factory_begin not in loc.paths
    assert "291/303/321" not in loc.seed_paths


def test_files_section_excludes_paths_from_other_sections():
    body = (
        "## Context\n`src/lokay/proc/factory_begin.py` is a counterexample.\n\n"
        "## Files\n- `src/lokay/localize.py`\n\n"
        "## Off-goal\nDo not clone `src/lokay/proc/commit_all.py`.\n"
    )
    seed_paths = extract_seed_paths(body)
    assert "src/lokay/localize.py" in seed_paths
    assert "src/lokay/proc/factory_begin.py" not in seed_paths
    assert "src/lokay/proc/commit_all.py" not in seed_paths


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
    (tmp_path / "fala" / "lokay.fala-package.toml").write_text(
        "id='x'\n", encoding="utf-8"
    )

    issue = _issue()
    seed = f"{issue.title}\n{issue.body}"
    loc = build_localization(worktree=tmp_path, seed_text=seed)
    assert loc.paths
    assert any("localize" in p for p in loc.paths)
    path = write_localize_file(tmp_path, loc)
    assert path == tmp_path / LOCALIZE_REL_PATH
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["paths"]


def test_issue_to_pr_localize_before_run_agent():
    desc = describe_package()
    path = next(p for p in desc["paths"] if p["id"] == "issue_to_pr_delivery")
    by_id = {n["id"]: n for n in path["nodes"]}
    assert "localize" in by_id
    assert "localize" in by_id["coding_execution"]["conduction"]
    assert "plan_issue" in by_id["localize"]["conduction"]
    assert "coding_execution" not in by_id["localize"]["conduction"]


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
    (tmp_path / "tests" / "test_runtime_evidence.py").write_text(
        "t\n", encoding="utf-8"
    )
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
    assert not any(p.startswith("influenzer/") and "brief" not in p for p in loc.paths)

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
    (pkg / "hom_verdict.py").write_text(
        "def verdict():\n    return 1\n", encoding="utf-8"
    )
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


def test_singleton_x_opens_platform_product_not_just_hn(tmp_path: Path):
    """influenzer#27: one-letter token X was dropped; HN/brief won the scope."""
    pkg = tmp_path / "influenzer"
    pkg.mkdir()
    (pkg / "playbook.py").write_text(
        "def score_x():\n    # twitter empty feed / tweet reply\n    return 1\n",
        encoding="utf-8",
    )
    (pkg / "brief_admit.py").write_text(
        "def admit():\n    return 'brief'\n", encoding="utf-8"
    )
    (pkg / "brief_scan.py").write_text(
        "def scan():\n    return 'hn'\n", encoding="utf-8"
    )
    (pkg / "unrelated.py").write_text("value = 1\n", encoding="utf-8")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_x_handoff.py").write_text(
        "from influenzer.playbook import score_x\n# https://twitter.com/intent/tweet\n",
        encoding="utf-8",
    )
    (tests / "test_brief_admit.py").write_text(
        "from influenzer.brief_admit import admit\n", encoding="utf-8"
    )
    (tests / "test_e2e_gates.py").write_text("gate = 1\n", encoding="utf-8")
    skills = tmp_path / "skills"
    skills.mkdir()
    (skills / "influenzer-hn").write_text("hn\n", encoding="utf-8")

    seed = (
        "X nie dostaje pustego feedu\n\n"
        "Repository: `mikolaj92/influenzer`\n"
        "Issue: #27 — X nie dostaje pustego feedu\n\n"
        "X nie dostaje pustego feedu. Score nie wybiera X, chyba ze brief ma URL. "
        "Ship bez watku -> github albo HN gdy tryable, inaczej cisza.\n"
    )
    loc = build_localization(worktree=tmp_path, seed_text=seed)
    assert "influenzer/playbook.py" in loc.paths, loc.paths
    assert "tests/test_x_handoff.py" in loc.paths, loc.paths
    assert "influenzer/unrelated.py" not in loc.paths
    assert "X" in loc.matched_tokens or "x" in {t.lower() for t in loc.matched_tokens}
    # HN/brief may still appear (seed names them) but must not cage out X product.
    assert (
        loc.paths.index("influenzer/playbook.py")
        < loc.paths.index("skills/influenzer-hn")
        or "skills/influenzer-hn" not in loc.paths
    )


def test_skill_hit_still_opens_identifier_product(tmp_path: Path):
    """influenzer#36/#40: a skill path is docs, not product; snake tokens live late in playbook."""
    pkg = tmp_path / "influenzer"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("\n", encoding="utf-8")
    padding = "# padding so the hook sits past the old 8KiB body window\n" * 400
    body = (
        padding
        + "def has_fair_hook(text):\n    return True\n"
        + "def choose_arena(kind):\n    return kind\n"
    )
    (pkg / "playbook.py").write_text(body, encoding="utf-8")
    (pkg / "unrelated.py").write_text("value = 1\n", encoding="utf-8")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_e2e_gates.py").write_text(
        "from influenzer.playbook import has_fair_hook, choose_arena\n",
        encoding="utf-8",
    )
    skills = tmp_path / "skills"
    (skills / "influenzer-shorts").mkdir(parents=True)
    (skills / "influenzer-shorts" / "SKILL.md").write_text(
        "Shorts skill. See playbook.\n", encoding="utf-8"
    )
    (skills / "influenzer-youtube").mkdir()
    (skills / "influenzer-youtube" / "SKILL.md").write_text(
        "YouTube skill.\n", encoding="utf-8"
    )

    seed = (
        "Shorts bez haczyka 1-3s = cisza\n\n"
        "Repository: `mikolaj92/influenzer`\n"
        "Issue: #36 — Shorts bez haczyka\n\n"
        "Shorts to swipe, nie VOD. `has_fair_hook` fail-closed. "
        "Ten sam cut co YouTube nie przechodzi.\n"
    )
    loc = build_localization(worktree=tmp_path, seed_text=seed)
    assert "influenzer/playbook.py" in loc.paths, loc.paths
    assert "influenzer/unrelated.py" not in loc.paths
    assert loc.paths.index("influenzer/playbook.py") < loc.paths.index(
        "tests/test_e2e_gates.py"
    )


def test_explicit_localization_atom_builds_closed_candidate():
    from lokay.proc.build_explicit_localization import build

    out = build(
        {"extras": [], "explicit_issue_paths": ["src/a.py"]},
        {"existing": []},
        {"route": "explicit"},
    )
    assert out["paths"] == ["src/a.py"] and out["source"] == "bypass"


def test_empty_seed_route_is_terminal():
    from lokay.proc.classify_localization_route import classify

    assert (
        classify(
            {"seed": "", "has_file_hints": False},
            {"existing": [], "worktree_exists": True},
            agent_allowed=True,
        )["route"]
        == "terminal"
    )


def test_invalid_agent_json_exposes_exact_validator_error():
    from lokay.proc.validate_localization_agent_json import validate

    out = validate({"route": "validate", "text": "not-json"})
    assert out["route"] == "invalid" and out["validator_error"]


LEFTOVER_333 = {
    "paths": [
        "src/lokay/proc/factory_begin.py",
        "hot.py",
        "lokay/proc/factory_begin.py",
        "tests/test_hot_repos.py",
    ],
    "source": "agent",
    "worktree": (
        "/Users/mini-m4-main/.lokay/worktrees/mikolaj92__lokay/"
        "ai__fix__333-factory_begin-cold-survey-musi-pokry-sko-1ddbe4a4"
    ),
}

_LEFTOVER_PATHS = (
    "src/lokay/proc/factory_begin.py",
    "tests/test_hot_repos.py",
)


def _write_localize(root: Path, payload: dict) -> None:
    loc = root / ".lokay"
    loc.mkdir(parents=True, exist_ok=True)
    (loc / "localize.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def test_leftover_333_localize_is_not_sieve_for_issue_865(tmp_path: Path):
    for rel in (*_LEFTOVER_PATHS, "src/lokay/localize.py"):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x\n", encoding="utf-8")
    _write_localize(tmp_path, LEFTOVER_333)
    seed = (
        "Issue #865 — leftover localize.json from main is not this ticket's sieve.\n"
        "Touch `src/lokay/localize.py`.\n"
    )
    from lokay.proc.build_deterministic_localization import build
    from lokay.proc.classify_localization_route import classify
    from lokay.proc.inspect_existing_localization import inspect

    request = {
        "worktree": str(tmp_path),
        "issue": 865,
        "seed": seed,
        "extras": [],
        "max_paths": 40,
        "explicit_issue_paths": [],
        "has_file_hints": False,
    }
    assert load_existing_localize_paths(tmp_path, issue=865) == []
    inspected = inspect(request)
    assert inspected["existing"] == []
    assert classify(request, inspected, agent_allowed=False)["route"] != "existing"
    loc = build(request)
    assert loc["source"] != "existing"
    assert "src/lokay/proc/factory_begin.py" not in loc["paths"]
    assert "tests/test_hot_repos.py" not in loc["paths"]
    det = build_localization(worktree=tmp_path, seed_text=seed)
    assert "src/lokay/proc/factory_begin.py" not in det.paths
    assert "tests/test_hot_repos.py" not in det.paths


def test_same_issue_localize_json_is_kept(tmp_path: Path):
    target = "src/lokay/localize.py"
    path = tmp_path / target
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x\n", encoding="utf-8")
    _write_localize(
        tmp_path,
        {
            "paths": [target],
            "source": "deterministic",
            "issue": 865,
            "worktree": str(tmp_path / "ai__fix__865-this-issue-sieve"),
        },
    )
    from lokay.proc.build_explicit_localization import build
    from lokay.proc.classify_localization_route import classify
    from lokay.proc.inspect_existing_localization import inspect

    request = {
        "worktree": str(tmp_path),
        "issue": 865,
        "seed": "Issue #865 reuse this ticket's localize.json.",
        "extras": [],
        "max_paths": 40,
        "explicit_issue_paths": [],
        "has_file_hints": False,
    }
    assert load_existing_localize_paths(tmp_path, issue=865) == [target]
    inspected = inspect(request)
    assert inspected["existing"] == [target]
    route = classify(request, inspected, agent_allowed=True)
    assert route["route"] == "existing"
    out = build(request, inspected, route)
    assert out["source"] == "existing"
    assert out["paths"] == [target]


def test_localize_json_without_issue_id_is_not_sieve(tmp_path: Path):
    _write_localize(tmp_path, {"paths": ["src/a.py"], "source": "deterministic"})
    assert load_existing_localize_paths(tmp_path, issue=865) == []
    assert localize_belongs_to_issue(tmp_path, 865) is False


def test_localize_belongs_to_issue_leftover_vs_this_issue_vs_unreadable(tmp_path: Path):
    _write_localize(tmp_path, LEFTOVER_333)
    assert localize_belongs_to_issue(tmp_path, 865) is False
    _write_localize(
        tmp_path,
        {
            "paths": ["src/lokay/localize.py"],
            "source": "deterministic",
            "issue": 865,
        },
    )
    assert localize_belongs_to_issue(tmp_path, 865) is True
    (tmp_path / LOCALIZE_REL_PATH).write_text("{not-json", encoding="utf-8")
    assert localize_belongs_to_issue(tmp_path, 865) is None
    assert localize_belongs_to_issue(None, 865) is None
