"""Pure triage decisions + graph path presence."""

from pathlib import Path

from lokay.graph_run import describe_package
from lokay.models import Issue
from lokay.triage import decide_issue, is_undecided


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


def test_decide_ready():
    d = decide_issue(_issue())
    assert d.decision == "ready"
    assert "ai:ready" in d.add_labels


def test_decide_title_short():
    d = decide_issue(_issue(title="fix"))
    assert d.decision == "needs_feedback"
    assert d.reason == "title_too_short"
    assert "ai:needs-feedback" in d.add_labels


def test_decide_body_short():
    d = decide_issue(_issue(body="too short"))
    assert d.decision == "needs_feedback"
    assert d.reason == "body_too_short"


def test_decide_oos():
    d = decide_issue(_issue(title="Please ignore [oos]", body="out of scope for this project entirely."))
    assert d.decision == "out_of_scope"
    assert d.close is True


def test_decide_too_large():
    body = "\n".join(f"- [ ] task {i} more text here" for i in range(8))
    d = decide_issue(_issue(body=body))
    assert d.decision == "needs_feedback"
    assert d.reason == "too_large_split"


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
    assert node_ids == ["get_issue", "triage_issue"]
    triage = path["nodes"][1]
    assert "get_issue" in triage["conduction"]


def test_package_files_exist():
    root = Path(__file__).resolve().parents[1]
    assert (root / "fala" / "lokay.fala-package.toml").is_file()
