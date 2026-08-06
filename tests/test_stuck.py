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
