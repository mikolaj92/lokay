"""Pure triage decisions + graph path presence."""

from pathlib import Path

from lokay.graph_run import describe_package
from lokay.models import Issue
from lokay.triage import decide_issue, is_parked, is_undecided


def _issue(**kwargs) -> Issue:
    base = dict(
        repo="a/b",
        number=1,
        title="Implement foo bar",
        body="Please add feature X with acceptance: does Y when Z.",
        labels=[],
        assignees=[],
        url="https://example.com/1",
    )
    base.update(kwargs)
    return Issue(**base)


def test_is_undecided():
    assert is_undecided([])
    assert is_undecided(["bug"])
    assert not is_undecided(["ai:ready"])
    assert not is_undecided(["ai:blocked"])
    assert not is_undecided(["ai:needs-feedback"])
    assert not is_undecided(["ai:in-progress"])
    assert not is_undecided(["ai:pr-open"])
    assert not is_undecided(["ai:ci-waiting"])
    assert not is_undecided(["ai:repairing"])
    assert not is_undecided(["frozen"])
    assert is_parked(["frozen"])
    assert is_parked(["ai:frozen"])
    assert not is_parked(["bug"])


def test_decide_skip_frozen():
    d = decide_issue(_issue(labels=["frozen", "enhancement"]))
    assert d.decision == "skip"
    assert d.reason == "parked_frozen"


def test_decide_ready():
    d = decide_issue(_issue())
    assert d.decision == "ready"
    assert "ai:ready" in d.add_labels
    assert "work:ready" in d.add_labels


def test_decide_preflight_incident_is_blocked():
    d = decide_issue(
        _issue(
            title="Preflight failure acae6d25447dc85e",
            body="<!-- lokay-preflight:acae6d25447dc85e -->\nBounded checks failed: fala_smoke",
        )
    )
    assert d.decision == "blocked"
    assert d.reason == "preflight_incident"
    assert "ai:blocked" in d.add_labels
    assert "work:ready" not in d.add_labels
    assert "ai:ready" not in d.add_labels


def test_decide_title_short():
    d = decide_issue(_issue(title="fix"))
    assert d.decision == "needs_feedback"
    assert d.reason == "title_too_short"
    assert "ai:needs-feedback" in d.add_labels


def test_decide_body_short():
    d = decide_issue(_issue(body="too short"))
    assert d.decision == "needs_feedback"
    assert d.reason == "body_too_short"


def test_decide_oos_title_marker():
    d = decide_issue(_issue(title="Please ignore [oos]", body="Please add feature X with acceptance: does Y when Z."))
    assert d.decision == "out_of_scope"
    assert d.close is True


def test_decide_oos_status_line():
    d = decide_issue(
        _issue(
            title="Legacy widget removal",
            body="Status: out of scope\n\nWe will not ship this path.",
        )
    )
    assert d.decision == "out_of_scope"
    assert d.reason == "oos_marker"


def test_decide_ready_despite_out_of_scope_section():
    """## Out of scope non-goals must NOT close real implementable bugs."""
    body = """## Goal
Make /ready fail when CT242 is down.

## Live repro
curl -sS -m 5 http://127.0.0.1:8000/ready

## Out of scope
- Fixing CT242 host availability itself (sibling ops issue)
- Changing search endpoint behavior (sibling hang-fix issue)

## Done means
- [ ] With CT242 down: GET /ready returns non-ready
"""
    d = decide_issue(_issue(title="Mnemozyna: /ready must probe CT242", body=body))
    assert d.decision == "ready", d
    assert d.close is False
    assert "ai:ready" in d.add_labels


def test_decide_ready_non_goals_heading():
    body = """## Goal
Fail closed knowledge endpoints on timeout.

## Non-goals
- Restoring CT242 host
- Vector embedding redesign

## Done means
- [ ] Endpoints return 503 within budget
"""
    d = decide_issue(
        _issue(title="Mnemozyna: knowledge endpoints fail closed", body=body)
    )
    assert d.decision == "ready", d




def test_decide_ready_with_parent_epic_footer():
    """Body 'Parent epic' must not force needs_feedback (only title epic does)."""
    body = """## Goal
Adopt full Basecoat + HTMX + Alpine stack via product_shell.

## Done means
- [ ] product_shell used
- [ ] No CDN for htmx

## Parent epic
- [Pad Audit] Platform UI + Fala unix processes + no-legacy epic (app-factory)
"""
    d = decide_issue(_issue(title="Platform UI audit: adopt full Basecoat stack", body=body))
    assert d.decision == "ready", d
    assert "ai:ready" in d.add_labels


def test_decide_split_title_epic():
    d = decide_issue(
        _issue(
            title="[Pad Audit] Platform UI + Fala unix processes + no-legacy epic (app-factory)",
            body="## Goal\nTrack child issues for platform audit.\n\n## Done means\n- [ ] children filed\n",
        )
    )
    assert d.decision == "split"
    assert d.reason == "too_large_split"
    assert d.add_labels == ()


def test_decide_too_large_splits():
    body = "\n".join(f"- [ ] task {i} more text here" for i in range(8))
    d = decide_issue(_issue(body=body))
    assert d.decision == "split"
    assert d.reason == "too_large_split"
    assert d.add_labels == ()


def test_decide_skip_already_ready():
    d = decide_issue(_issue(labels=["ai:ready"]))
    assert d.decision == "skip"


def test_issue_triage_path_in_package():
    desc = describe_package()
    ids = [p["id"] for p in desc["paths"]]
    assert "issue_to_pr" in ids
    assert "issue_triage" in ids
    path = next(p for p in desc["paths"] if p["id"] == "issue_triage")
    node_ids = [n["id"] for n in path["nodes"]]
    assert node_ids == ["get_issue", "triage_issue", "intake_issue", "issue_split"]
    triage = path["nodes"][1]
    assert "get_issue" in triage["conduction"]
    intake = path["nodes"][2]
    assert "triage_issue" in intake["conduction"]
    split = path["nodes"][3]
    assert "intake_issue" in split["conduction"]


def test_pr_repair_path_in_package():
    desc = describe_package()
    ids = [p["id"] for p in desc["paths"]]
    assert "pr_repair" in ids
    path = next(p for p in desc["paths"] if p["id"] == "pr_repair")
    node_ids = [n["id"] for n in path["nodes"]]
    assert node_ids == [
        "pr_checks",
        "stage_repairing",
        "worktree_add",
        "localize",
        "run_agent",
        "commit_all",
        "test_local",
        "assert_real_diff",
        "push",
    ]
    agent = next(n for n in path["nodes"] if n["id"] == "run_agent")
    assert "worktree_add" in agent["conduction"]
    assert "localize" in agent["conduction"]
    assert "pr_checks" in agent["conduction"]
    localize = next(n for n in path["nodes"] if n["id"] == "localize")
    assert "worktree_add" in localize["conduction"]
    assert "pr_checks" in localize["conduction"]
    stage = next(n for n in path["nodes"] if n["id"] == "stage_repairing")
    assert "pr_checks" in stage["conduction"]


def test_pr_triage_path_in_package():
    desc = describe_package()
    ids = [p["id"] for p in desc["paths"]]
    assert "pr_triage" in ids
    path = next(p for p in desc["paths"] if p["id"] == "pr_triage")
    node_ids = [n["id"] for n in path["nodes"]]
    assert node_ids == [
        "pr_checks",
        "collect_pr_review_evidence",
        "resolve_sha_review",
        "pr_review_agent",
        "validate_pr_review",
        "pr_review_retry_agent",
        "validate_pr_review_retry",
        "select_pr_review",
        "collect_review_pr_metadata",
        "collect_review_changed_files",
        "collect_review_diff_tail",
        "collect_review_commit_history",
        "verify_review_evidence_sha",
        "evidence_review_agent",
        "validate_evidence_review",
        "select_evidence_review",
        "finalize_pr_review",
        "publish_pr_review",
        "review_repair_gate",
        "pr_repair_subflow",
        "review_repair_manual",
        "review_manual",
        "worktree_add",
        "test_local",
        "pr_merge",
        "stage_clear",
        "close_issue",
    ]
    assert "run_agent" not in node_ids
    collect = next(n for n in path["nodes"] if n["id"] == "collect_pr_review_evidence")
    assert "pr_checks" in collect["conduction"]
    retry = next(n for n in path["nodes"] if n["id"] == "pr_review_retry_agent")
    assert retry["when"] == {"upstream": "validate_pr_review", "path": "route", "equals": "retry"}
    worktree = next(n for n in path["nodes"] if n["id"] == "worktree_add")
    assert "publish_pr_review" in worktree["conduction"]
    merge = next(n for n in path["nodes"] if n["id"] == "pr_merge")
    assert "pr_checks" in merge["conduction"]
    assert "publish_pr_review" in merge["conduction"]
    assert "test_local" in merge["conduction"]
    clear = next(n for n in path["nodes"] if n["id"] == "stage_clear")
    assert "pr_merge" in clear["conduction"]
    close = next(n for n in path["nodes"] if n["id"] == "close_issue")
    assert "pr_merge" in close["conduction"]
    assert "stage_clear" in close["conduction"]
    assert "publish_pr_review" in close["conduction"]


def test_package_files_exist():
    root = Path(__file__).resolve().parents[1]
    assert (root / "fala" / "lokay.fala-package.toml").is_file()
