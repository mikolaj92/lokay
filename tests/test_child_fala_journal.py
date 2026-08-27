"""Isolated Fala journals for issue-to-PR and coding_execution children."""

from __future__ import annotations

import json
from pathlib import Path

from lokay.proc.child_fala_journal import journal_dir, main


def test_coding_execution_journal_is_not_shared_host_sqlite(tmp_path: Path):
    first = journal_dir(
        path_id="coding_execution",
        repo="mikolaj92/Temida",
        issue=4999,
        home=tmp_path,
    )
    second = journal_dir(
        path_id="coding_execution",
        repo="mikolaj92/Temida",
        issue=4996,
        home=tmp_path,
    )
    shared = tmp_path / ".lokay" / "fala"
    assert first != second
    assert first != shared and second != shared
    assert first.name.endswith("4999")
    assert (first / "state.sqlite").parent == first
    assert "coding" in first.parts


def test_issue_to_pr_journal_stays_per_ticket(tmp_path: Path):
    work = journal_dir(
        path_id="issue_to_pr",
        repo="mikolaj92/lokay",
        issue=842,
        home=tmp_path,
    )
    assert work == tmp_path / ".lokay" / "fala" / "i2pr" / "mikolaj92__lokay__842"


def test_factory_pass_keeps_host_root(tmp_path: Path):
    work = journal_dir(
        path_id="factory_pass",
        repo="__lokay_factory__",
        issue=None,
        home=tmp_path,
    )
    assert work == tmp_path / ".lokay" / "fala"


def test_cli_prints_isolated_coding_journal(tmp_path: Path, capsys):
    code = main(
        [
            "--path-id",
            "coding_execution",
            "--repo",
            "mikolaj92/Temida",
            "--issue",
            "4997",
            "--lokay-home",
            str(tmp_path),
        ]
    )
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["path_id"] == "coding_execution"
    assert out["dir"].endswith("coding/mikolaj92__Temida__4997")
    assert out["db"].endswith("state.sqlite")
