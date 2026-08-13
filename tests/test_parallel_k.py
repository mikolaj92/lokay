"""Hermetic tests for lokay-parallel-k (K-cap + per-repo mutex)."""

from __future__ import annotations

import io
import json
import sys

from lokay.proc.parallel_k import main, run_parallel_k, select_k


def _cli(monkeypatch, capsys, issues: list[dict], argv: list[str] | None = None):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(issues)))
    code = main(argv or [])
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    return code, out


def test_two_issues_same_repo_selects_one():
    issues = [
        {"repo": "a/one", "number": 3},
        {"repo": "a/one", "number": 1},
    ]
    selected = select_k(issues, k=4)
    assert len(selected) == 1
    assert selected == [{"repo": "a/one", "number": 1}]


def test_four_repos_selects_four():
    issues = [
        {"repo": "d/four", "number": 40},
        {"repo": "b/two", "number": 20},
        {"repo": "c/three", "number": 30},
        {"repo": "a/one", "number": 10},
    ]
    selected = select_k(issues, k=4)
    assert len(selected) == 4
    assert selected == [
        {"repo": "a/one", "number": 10},
        {"repo": "b/two", "number": 20},
        {"repo": "c/three", "number": 30},
        {"repo": "d/four", "number": 40},
    ]


def test_cli_same_repo_mutex_and_four_repos(monkeypatch, capsys):
    code, out = _cli(
        monkeypatch,
        capsys,
        [
            {"repo": "a/one", "number": 2},
            {"repo": "a/one", "number": 1},
        ],
    )
    assert code == 0
    assert out["ok"] is True
    assert len(out["selected"]) == 1
    assert out["selected"][0]["number"] == 1

    code, out = _cli(
        monkeypatch,
        capsys,
        [
            {"repo": "w/four", "number": 4},
            {"repo": "x/one", "number": 1},
            {"repo": "y/two", "number": 2},
            {"repo": "z/three", "number": 3},
        ],
    )
    assert code == 0
    assert len(out["selected"]) == 4


def test_k_caps_and_empty_list():
    issues = [
        {"repo": "a/one", "number": 1},
        {"repo": "b/two", "number": 2},
        {"repo": "c/three", "number": 3},
    ]
    assert len(select_k(issues, k=2)) == 2
    assert run_parallel_k([], k=4)["selected"] == []
    assert run_parallel_k({"issues": []}, k=4)["ok"] is False
