"""Stuck-issue isolation and select exclude."""

import json
from pathlib import Path

from lokay.proc.select_issue import main as select_main
from lokay.stuck import (
    clear_issue,
    excluded_numbers,
    issue_number_from_branch,
    load_stuck,
    record_failure,
    save_stuck,
    stuck_path_for,
)


def test_issue_number_from_branch():
    assert issue_number_from_branch("ai/fix/12-hello-world-abcdef12") == 12
    assert issue_number_from_branch("ai/fix/3-canary-58b8306c") == 3
    assert issue_number_from_branch("main") is None
    assert issue_number_from_branch("feature/foo") is None


def test_issue_numbers_covered_by_prs():
    from lokay.stuck import issue_numbers_covered_by_prs

    prs = [
        {"number": 2, "head_ref": "ai/fix/1-canary-b9ef84f6"},
        {"number": 4, "head_ref": "ai/fix/3-canary-58b8306c"},
        {"number": 9, "head_ref": "main"},
    ]
    assert issue_numbers_covered_by_prs(prs) == {1, 3}


def test_record_failure_blocks_after_threshold(tmp_path: Path):
    path = stuck_path_for(tmp_path / "state.jsonl")
    data = load_stuck(path)
    row1 = record_failure(data, repo="a/b", number=7, error="boom1", max_failures=2)
    assert row1["failures"] == 1
    assert not row1.get("blocked")
    row2 = record_failure(data, repo="a/b", number=7, error="boom2", max_failures=2)
    assert row2["failures"] == 2
    assert row2.get("blocked") is True
    save_stuck(path, data)
    reloaded = load_stuck(path)
    assert excluded_numbers(reloaded, "a/b") == {7}
    assert excluded_numbers(reloaded, "other/r") == set()
    clear_issue(reloaded, "a/b", 7)
    assert excluded_numbers(reloaded, "a/b") == set()


def test_save_stuck_preserves_blocked_issue_missing_from_incoming(tmp_path: Path):
    path = tmp_path / "stuck.json"
    path.write_text(
        json.dumps(
            {
                "issues": {
                    "a/b#1": {"failures": 2, "blocked": True},
                    "a/b#2": {"failures": 1, "blocked": True},
                }
            }
        ),
        encoding="utf-8",
    )

    save_stuck(path, {"issues": {"a/b#2": {"failures": 2}}})

    # Incoming data wins when a blocked issue is present in both snapshots.

    saved = load_stuck(path)
    assert saved["issues"]["a/b#1"]["blocked"] is True
    assert saved["issues"]["a/b#2"]["failures"] == 2
    assert saved["issues"]["a/b#2"].get("blocked") is None


def test_save_stuck_cleared_no_pr_is_not_restored(tmp_path: Path):
    path = tmp_path / "stuck.json"
    path.write_text(
        json.dumps(
            {
                "issues": {
                    "a/b#5": {"failures": 1, "blocked": True, "reason": "no_pr"},
                    "a/b#6": {"failures": 1, "blocked": True, "reason": "plan_only"},
                }
            }
        ),
        encoding="utf-8",
    )
    save_stuck(
        path,
        {"issues": {}, "cleared": ["a/b#5"]},
    )
    saved = load_stuck(path)
    assert "a/b#5" not in saved["issues"]
    assert saved["issues"]["a/b#6"]["blocked"] is True
    assert "cleared" not in saved


def test_select_skips_excluded(monkeypatch, capsys):
    payload = {
        "issues": [
            {
                "repo": "a/b",
                "number": 1,
                "title": "stuck",
                "body": "x",
                "labels": ["ai:ready"],
                "assignees": [],
                "url": "u1",
            },
            {
                "repo": "a/b",
                "number": 3,
                "title": "next",
                "body": "y",
                "labels": ["ai:ready"],
                "assignees": [],
                "url": "u3",
            },
        ],
        "exclude": [1],
    }
    import io
    import sys

    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    code = select_main([])
    assert code == 0
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["ok"] is True
    assert out["selected"]["number"] == 3


def test_select_all_excluded(monkeypatch, capsys):
    payload = {
        "issues": [
            {
                "repo": "a/b",
                "number": 1,
                "title": "stuck",
                "body": "x",
                "labels": [],
                "assignees": [],
                "url": "u",
            }
        ],
        "exclude": [1],
    }
    import io
    import sys

    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    code = select_main([])
    assert code == 0
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["selected"] is None
    assert out["reason"] == "all_excluded"
