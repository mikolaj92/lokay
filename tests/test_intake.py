"""Deterministic intake checks + graph / mill gate."""

from __future__ import annotations

from pathlib import Path

from lokay.graph_run import describe_package, normalize_path_result
from lokay.intake import (
    check_ambiguity,
    check_duplicate_ai_pr,
    check_essence_objection,
    check_open,
    check_preflight_incident,
    check_satisfied,
    check_shape,
    check_superseded,
    decide_intake,
    probe_repo_shape,
    should_run_intake,
)
from lokay.models import Issue


def _issue(**kwargs) -> Issue:
    base = dict(
        repo="a/b",
        number=1,
        title="Implement foo bar baz",
        body="Please add feature X with acceptance: does Y when Z happens.",
        labels=["ai:ready"],
        assignees=[],
        url="https://example.com/1",
        state="OPEN",
    )
    base.update(kwargs)
    return Issue(**base)


def test_check_open_closed():
    assert check_open(state="OPEN").verdict == "pass"
    closed = check_open(state="CLOSED")
    assert closed.verdict == "close"
    assert closed.reason == "issue_already_closed"


def test_shape_closes_platform_work_on_library(tmp_path: Path):
    (tmp_path / "README.md").write_text(
        "# Cool Kit\n\nA small library SDK.\n", encoding="utf-8"
    )
    (tmp_path / "src" / "coolkit").mkdir(parents=True)
    (tmp_path / "src" / "coolkit" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "coolkit"\n', encoding="utf-8"
    )
    shape = probe_repo_shape(tmp_path)
    assert shape.kind == "library", shape
    issue = _issue(
        title="Platform UI audit: adopt full Basecoat + product_shell",
        body="## Goal\nAdopt product_shell and /static/platform Basecoat stack.\n\n## Done means\n- [ ] product_shell used\n",
    )
    result = check_shape(issue, shape)
    assert result.verdict == "close"
    assert result.reason == "wrong_product_shape"


def test_shape_closes_platform_work_on_swift_only(tmp_path: Path):
    (tmp_path / "Package.swift").write_text(
        "// swift-tools-version: 5.9\n", encoding="utf-8"
    )
    (tmp_path / "Sources").mkdir()
    shape = probe_repo_shape(tmp_path)
    assert shape.kind == "library", shape
    issue = _issue(
        title="Adopt product_shell host chrome",
        body="Wire product_shell and Basecoat /static/platform.\n",
    )
    assert check_shape(issue, shape).verdict == "close"


def test_shape_allows_platform_work_on_host(tmp_path: Path):
    (tmp_path / "README.md").write_text("# Host app\n", encoding="utf-8")
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "product_shell.html").write_text(
        "<html></html>", encoding="utf-8"
    )
    (tmp_path / "static" / "platform").mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text(
        'dependencies = ["fastapi", "app-factory"]\n', encoding="utf-8"
    )
    shape = probe_repo_shape(tmp_path)
    assert shape.kind == "host", shape
    issue = _issue(
        title="Adopt product_shell host chrome",
        body="Extend product_shell; load /static/platform assets.\n\nDone: shell used.",
    )
    assert check_shape(issue, shape).verdict == "pass"


def test_satisfied_closes_when_paths_already_gone(tmp_path: Path):
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    issue = _issue(
        title="Remove legacy shim",
        body="Please remove `src/legacy/shim.py` and delete src/old/compat.py from main.",
    )
    result = check_satisfied(issue, clone_path=tmp_path)
    assert result.verdict == "close"
    assert result.reason == "already_satisfied_on_main"


def test_satisfied_closes_when_feature_present(tmp_path: Path):
    path = tmp_path / "src" / "feature" / "new.py"
    path.parent.mkdir(parents=True)
    path.write_text("ok", encoding="utf-8")
    issue = _issue(
        title="Add feature module",
        body="Please add `src/feature/new.py` for the parser.",
    )
    result = check_satisfied(issue, clone_path=tmp_path)
    assert result.verdict == "close"
    assert result.reason == "feature_already_present"


def test_satisfied_closes_already_on_main_marker():
    issue = _issue(
        title="Wire parser",
        body="This is already on main after the last merge.\n\nNo further work.",
    )
    result = check_satisfied(issue, clone_path=None)
    assert result.verdict == "close"
    assert result.reason == "already_on_main_marker"


def test_satisfied_passes_when_target_still_present(tmp_path: Path):
    path = tmp_path / "src" / "legacy" / "shim.py"
    path.parent.mkdir(parents=True)
    path.write_text("x", encoding="utf-8")
    issue = _issue(
        title="Remove legacy shim",
        body="Please remove `src/legacy/shim.py` now.",
    )
    assert check_satisfied(issue, clone_path=tmp_path).verdict == "pass"


def test_ambiguity_inventory_splits_not_human():
    issue = _issue(
        title="Inventory everything in the monorepo",
        body="Please inventory everything and audit all modules for legacy.\n" * 3,
    )
    result = check_ambiguity(issue)
    assert result.verdict == "split"
    assert result.reason == "inventory_everything"


def test_ambiguity_too_many_checkboxes_splits():
    body = "\n".join(f"- [ ] task {i} more text here for slice" for i in range(8))
    result = check_ambiguity(_issue(body=body))
    assert result.verdict == "split"
    assert result.reason == "too_many_checkboxes"


def test_duplicate_ai_pr_closes():
    issue = _issue(number=12)
    result = check_duplicate_ai_pr(
        issue,
        covering_prs=[{"number": 44, "state": "OPEN", "merged": False}],
    )
    assert result.verdict == "close"
    assert result.reason == "duplicate_ai_pr_for_issue"


def test_tracker_closed_superseded():
    issue = _issue(title="Platform audit epic tracker", body="Track children.")
    result = check_superseded(issue, closed_tracker_done=True)
    assert result.verdict == "close"
    assert result.reason == "tracker_already_done"


def test_essence_closes_foreign_soul_objection():
    issue = _issue(
        author="stranger",
        assignees=[],
        title="Lokay should be a kanban not a mill",
        body="Wrong philosophy. Change the soul / kwintesencja of the product.",
    )
    result = check_essence_objection(issue)
    assert result.verdict == "close"
    assert result.reason == "foreign_essence_objection"
    d = decide_intake(issue, clone_path=None, state="OPEN")
    assert d.decision == "close"
    assert d.reason == "foreign_essence_objection"
    assert "hangs" in (d.comment or "")


def test_essence_keeps_operator_rewrite():
    issue = _issue(
        author="mikolaj92",
        assignees=["mikolaj92"],
        title="Rewrite the soul of the mill",
        body="Kwintesencja ma być inna. Zmienić wizję produktu.",
    )
    result = check_essence_objection(issue)
    assert result.verdict == "pass"
    assert result.reason == "operator_authored"


def test_essence_keeps_foreign_hang_report():
    issue = _issue(
        author="stranger",
        assignees=[],
        title="Mill hangs on issue_to_pr",
        body="Does not work as described: daemon stuck after survey, no merge.",
    )
    result = check_essence_objection(issue)
    assert result.verdict == "pass"
    assert result.reason == "operational_report"


def test_decide_intake_ready_path(tmp_path: Path):
    (tmp_path / "README.md").write_text("# App\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="app"\n', encoding="utf-8"
    )
    # Ordinary implementable bugfix — not a platform-host playbook.
    d = decide_intake(_issue(), clone_path=tmp_path, state="OPEN")
    assert d.decision == "ready", d
    assert d.implementable is True
    assert "ai:ready" in d.add_labels
    assert "work:ready" in d.add_labels


def test_decide_intake_blocks_preflight_incident(tmp_path: Path):
    (tmp_path / "README.md").write_text("# App\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="app"\n', encoding="utf-8"
    )
    issue = _issue(
        title="Preflight failure 7a069cefb68040e2",
        body="<!-- lokay-preflight:7a069cefb68040e2 -->\nBounded checks failed: disk_headroom",
        labels=["ai:ready", "work:ready"],
    )
    hit = check_preflight_incident(issue)
    assert hit.verdict == "blocked"
    d = decide_intake(issue, clone_path=tmp_path, state="OPEN")
    assert d.decision == "blocked"
    assert d.implementable is False
    assert "ai:blocked" in d.add_labels
    assert "work:ready" in d.remove_labels


def test_decide_intake_obsolete_close_on_library(tmp_path: Path):
    (tmp_path / "README.md").write_text("A pure library kit.\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="kit"\n', encoding="utf-8"
    )
    d = decide_intake(
        _issue(
            title="Adopt product_shell / Basecoat host stack",
            body="Wire product_shell and /static/platform for auth chrome.\n\nDone means shell renders.",
        ),
        clone_path=tmp_path,
        state="OPEN",
    )
    assert d.decision == "close"
    assert d.close is True
    assert d.implementable is False
    assert (
        "product_shell" in (d.comment or "").lower()
        or "library" in (d.comment or "").lower()
    )


def test_decide_intake_split_on_inventory(tmp_path: Path):
    (tmp_path / "README.md").write_text("# App\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    d = decide_intake(
        _issue(
            title="Inventory everything across modules",
            body="Please inventory everything in the tree and list follow-ups.\n" * 2,
        ),
        clone_path=tmp_path,
    )
    assert d.decision == "split"
    assert d.implementable is False
    assert "Split" in (d.comment or "")


def test_decide_intake_never_ready_on_inconclusive(tmp_path: Path):
    # Removal paths named but clone missing → fail closed, not READY.
    d = decide_intake(
        _issue(
            title="Remove legacy shim file",
            body="Please remove `src/legacy/shim.py` from the tree now.",
        ),
        clone_path=None,
    )
    assert d.decision == "needs_human"
    assert d.implementable is False


def test_issue_triage_path_includes_intake_and_split():
    desc = describe_package()
    path = next(p for p in desc["paths"] if p["id"] == "issue_triage")
    node_ids = [n["id"] for n in path["nodes"]]
    assert node_ids == [
        "get_issue",
        "resolve_issue_candidate",
        "collect_issue_linked_prs",
        "collect_issue_covering_prs",
        "resolve_issue_hard_facts",
        "issue_triage_agent",
        "validate_issue_triage",
        "issue_triage_retry_agent",
        "validate_issue_triage_retry",
        "select_issue_triage",
        "collect_issue_repo_shape",
        "collect_issue_named_paths",
        "verify_issue_evidence",
        "issue_evidence_agent",
        "validate_issue_evidence",
        "select_issue_evidence",
        "finalize_issue_triage",
        "apply_issue_blocked",
        "apply_issue_mark",
        "apply_issue_ready",
        "apply_issue_skip",
        "apply_issue_manual",
        "summarize_issue_triage",
    ]
    linked = path["nodes"][2]
    assert "resolve_issue_candidate" in linked["conduction"]
    assert "get_issue" in linked["conduction"]
    skip = next(node for node in path["nodes"] if node["id"] == "apply_issue_skip")
    assert "finalize_issue_triage" in skip["conduction"]
    assert all(node["id"] != "issue_split_subflow" for node in path["nodes"])






def _gate(**kwargs):
    kw = dict(
        ready_label="ai:ready",
        needs_feedback_label="ai:needs-feedback",
        blocked_label="ai:blocked",
    )
    kw.update(kwargs)
    return should_run_intake(**kw)


def test_should_run_intake_ready_and_candidates():
    assert _gate(issue_labels=["ai:ready"]) == (True, "already_ready")
    assert _gate(issue_labels=[], candidate_split=True) == (
        True,
        "triage_split_candidate",
    )
    assert _gate(issue_labels=[], candidate_ready=True) == (
        True,
        "triage_ready_candidate",
    )


def test_should_run_intake_skips_parked_blocked_undecided():
    assert _gate(issue_labels=["frozen"]) == (False, "parked_frozen")
    assert _gate(issue_labels=["ai:blocked"]) == (False, "blocked")
    assert _gate(issue_labels=["ai:needs-feedback"]) == (False, "needs_feedback")
    assert _gate(issue_labels=[]) == (False, "undecided_await_triage")
    assert _gate(issue_labels=["ai:in-progress"]) == (False, "not_ready_candidate")
