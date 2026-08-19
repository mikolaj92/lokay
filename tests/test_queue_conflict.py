"""Contradiction / queue-conflict gate — hermetic unit tests."""

from __future__ import annotations

import pytest

from lokay.models import Issue
from lokay.passkit import io as pass_io
from lokay.proc import queue_conflict as queue_conflict_proc
from lokay.queue_conflict import (
    CLOSE,
    READY,
    SKIP,
    ConflictVerdict,
    evaluate_queue_conflict,
)
from lokay.proc.queue_conflict import evaluate_stdin


def _issue(**kwargs) -> Issue:
    base = {
        "repo": "a/lib",
        "number": 10,
        "title": "Fix parser",
        "body": "Handle empty input.\n",
        "labels": ["ai:ready"],
        "assignees": ["mikolaj92"],
        "url": "https://example.test/10",
        "state": "OPEN",
    }
    base.update(kwargs)
    return Issue(**base)


def test_ready_when_no_contradiction():
    v = evaluate_queue_conflict(_issue())
    assert v.outcome == READY
    assert v.reason == "no_clear_contradiction"


def test_close_when_open_ai_pr_covers_issue():
    v = evaluate_queue_conflict(
        _issue(number=12),
        open_prs=[
            {
                "number": 99,
                "head_ref": "ai/fix/12-fix-parser",
                "title": "Fix parser",
                "body": "Fixes #12",
            }
        ],
    )
    assert v.outcome == CLOSE
    assert v.reason == "open_ai_pr_covers_issue"
    assert "ai:ready" in v.remove_labels


def test_close_when_superseded_by_open_pr():
    v = evaluate_queue_conflict(
        _issue(number=5, title="Old approach"),
        open_prs=[
            {
                "number": 40,
                "head_ref": "ai/fix/40-new",
                "title": "New approach",
                "body": "Supersedes #5\n",
            }
        ],
    )
    assert v.outcome == CLOSE
    assert v.reason == "superseded_by_open_pr"


def test_demote_epic_when_children_exist():
    epic = _issue(
        number=1,
        title="Platform audit epic",
        body="- [ ] one\n- [ ] two\n",
        labels=["ai:ready"],
    )
    child = {
        "number": 2,
        "title": "Child: adopt product_shell",
        "body": "## Parent epic\nSee #1\nParent epic #1\n",
        "labels": ["ai:ready"],
    }
    v = evaluate_queue_conflict(epic, peer_issues=[child])
    assert v.outcome == CLOSE
    assert v.reason == "epic_has_children_prefer_children"
    assert "ai:tracker" in v.add_labels
    assert "ai:ready" in v.remove_labels


def test_child_ready_when_parent_is_tracker_not_ready_peer():
    """Children proceed; only the epic candidate is demoted."""
    child = _issue(
        number=2,
        title="Child work",
        body="Parent epic #1\nTouch `src/lokay/cli.py`.\n",
    )
    v = evaluate_queue_conflict(
        child,
        peer_issues=[
            {
                "number": 1,
                "title": "Epic tracker",
                "body": "tracking",
                "labels": ["ai:tracker"],
            }
        ],
    )
    assert v.outcome == READY


def test_skip_when_dependency_unmet():
    v = evaluate_queue_conflict(
        _issue(
            number=8,
            title="Follow-up",
            body="Depends on #3\n",
        ),
        peer_issues=[
            {"number": 3, "title": "Prerequisite", "body": "still open", "labels": []}
        ],
    )
    assert v.outcome == SKIP
    assert v.reason == "dependency_unmet"
    assert v.detail["depends_on"] == [3]


def test_skip_path_overlap_defers_newer_issue():
    older = {
        "number": 4,
        "title": "Touch cli",
        "body": "Edit `src/lokay/cli.py`\n",
        "labels": ["ai:ready"],
    }
    newer = _issue(
        number=9,
        title="Also touch cli",
        body="Also edit `src/lokay/cli.py`\n",
    )
    v = evaluate_queue_conflict(newer, peer_issues=[older])
    assert v.outcome == SKIP
    assert v.reason == "path_overlap_with_peer"


def test_older_with_path_overlap_stays_ready():
    newer = {
        "number": 9,
        "title": "Also touch cli",
        "body": "Also edit `src/lokay/cli.py`\n",
        "labels": ["ai:ready"],
    }
    older = _issue(
        number=4,
        title="Touch cli",
        body="Edit `src/lokay/cli.py`\n",
    )
    v = evaluate_queue_conflict(older, peer_issues=[newer])
    assert v.outcome == READY


@pytest.mark.parametrize("repo", ["mikolaj92/Temida", "mikolaj92/takt"])
def test_stdin_skips_product_repos_without_evaluating(repo, monkeypatch):
    monkeypatch.setattr(
        queue_conflict_proc,
        "evaluate_queue_conflict_with_agent",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("product repo reached semantic agent")
        ),
    )

    out = evaluate_stdin({"issue": _issue(repo=repo).to_dict()})

    assert out["ok"] is True
    assert out["outcome"] == SKIP
    assert out["reason"] == "repo_not_delivered_by_mini_mill"
    assert out["selected"] is None


def test_pass_mode_skips_products_and_evaluates_lokay(tmp_path, monkeypatch):
    product = _issue(repo="mikolaj92/Temida", number=20).to_dict()
    lokay = _issue(repo="mikolaj92/lokay", number=21).to_dict()
    pass_io.write_json(
        pass_io.begin_path(tmp_path),
        {"repos": ["mikolaj92/Temida", "mikolaj92/lokay"]},
    )
    pass_io.write_json(
        pass_io.working_path(tmp_path),
        {
            "actions": [],
            "ready_by_repo": {
                "mikolaj92/Temida": [product],
                "mikolaj92/lokay": [lokay],
            },
            "remaining_ready": 2,
        },
    )
    pass_io.write_json(
        pass_io.implement_path(tmp_path),
        {"clean_repos": ["mikolaj92/Temida", "mikolaj92/lokay"]},
    )
    called: list[str] = []

    def evaluate(issue, **_kwargs):
        called.append(issue["repo"])
        return ConflictVerdict(READY, "no_clear_contradiction")

    monkeypatch.setattr(
        queue_conflict_proc, "evaluate_queue_conflict_with_agent", evaluate
    )

    out = queue_conflict_proc.run_queue_conflict(
        pass_dir=str(tmp_path), config_path=None, live=False
    )

    assert out["ok"] is True
    assert out["skipped"] == 1
    assert called == ["mikolaj92/lokay"]
    working = pass_io.read_json(pass_io.working_path(tmp_path))
    assert working["ready_by_repo"]["mikolaj92/Temida"] == []
    assert working["remaining_ready"] == 1
    assert pass_io.read_json(pass_io.implement_path(tmp_path))["clean_repos"] == [
        "mikolaj92/lokay"
    ]


def test_stdin_envelope_selects_only_when_ready():
    out = evaluate_stdin(
        {
            "issue": _issue(repo="mikolaj92/lokay", number=12).to_dict(),
            "open_prs": [
                {
                    "number": 99,
                    "head_ref": "ai/fix/12-x",
                    "title": "x",
                    "body": "",
                }
            ],
        }
    )
    assert out["ok"] is True
    assert out["outcome"] == CLOSE
    assert out["selected"] is None
