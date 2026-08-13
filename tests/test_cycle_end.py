"""Hermetic tests for lokay-cycle-end (tmp dir; no Fala / GitHub)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from lokay.proc import cycle_end


def _payload(capsys) -> dict:
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def _write_start(tmp_path: Path, *, repo: str, issue: int, started_ts: str) -> Path:
    owner, name = repo.split("/")
    path = tmp_path / f"{owner}__{name}__{issue}.json"
    path.write_text(
        json.dumps({"repo": repo, "issue": issue, "started_ts": started_ts}) + "\n",
        encoding="utf-8",
    )
    return path


def test_minutes_within_budget(tmp_path: Path, capsys):
    _write_start(tmp_path, repo="owner/name", issue=42, started_ts="2026-08-13T16:00:00Z")
    code = cycle_end.main(
        [
            "--repo",
            "owner/name",
            "--issue",
            "42",
            "--dir",
            str(tmp_path),
            "--pr-opened-ts",
            "2026-08-13T16:08:00Z",
        ]
    )
    assert code == 0
    out = _payload(capsys)
    assert out["ok"] is True
    assert out["repo"] == "owner/name"
    assert out["issue"] == 42
    assert out["minutes"] == 8
    assert out["ok_budget"] is True


def test_exactly_ten_minutes_is_within_budget(tmp_path: Path, capsys):
    _write_start(tmp_path, repo="acme/lib", issue=7, started_ts="2026-08-13T16:00:00Z")
    code = cycle_end.main(
        [
            "--repo",
            "acme/lib",
            "--issue",
            "7",
            "--dir",
            str(tmp_path),
            "--pr-opened-ts",
            "2026-08-13T16:10:00Z",
        ]
    )
    assert code == 0
    out = _payload(capsys)
    assert out["minutes"] == 10
    assert out["ok_budget"] is True


def test_over_budget(tmp_path: Path, capsys):
    _write_start(tmp_path, repo="owner/name", issue=3, started_ts="2026-08-13T16:00:00Z")
    code = cycle_end.main(
        [
            "--repo",
            "owner/name",
            "--issue",
            "3",
            "--dir",
            str(tmp_path),
            "--pr-opened-ts",
            "2026-08-13T16:11:00Z",
        ]
    )
    assert code == 0
    out = _payload(capsys)
    assert out["ok"] is True
    assert out["minutes"] == 11
    assert out["ok_budget"] is False


def test_missing_start_file_fails_closed(tmp_path: Path, capsys):
    code = cycle_end.main(
        ["--repo", "owner/name", "--issue", "99", "--dir", str(tmp_path)]
    )
    assert code == 1
    out = _payload(capsys)
    assert out["ok"] is False
    assert "missing" in out["error"]
    assert out["repo"] == "owner/name"
    assert out["issue"] == 99
    assert out["path"] == str(tmp_path / "owner__name__99.json")


def test_default_dir_is_home_lokay_cycle(tmp_path: Path, monkeypatch, capsys):
    home = tmp_path / "home"
    dest = home / ".lokay" / "cycle"
    dest.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    _write_start(dest, repo="a/b", issue=1, started_ts="2026-08-13T12:00:00Z")
    code = cycle_end.main(
        ["--repo", "a/b", "--issue", "1", "--pr-opened-ts", "2026-08-13T12:04:00Z"]
    )
    assert code == 0
    out = _payload(capsys)
    assert out["ok"] is True
    assert out["minutes"] == 4
    assert out["ok_budget"] is True


def test_now_when_pr_opened_ts_omitted(tmp_path: Path, capsys):
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _write_start(tmp_path, repo="owner/name", issue=5, started_ts=started)
    code = cycle_end.main(
        ["--repo", "owner/name", "--issue", "5", "--dir", str(tmp_path)]
    )
    assert code == 0
    out = _payload(capsys)
    assert out["ok"] is True
    assert out["minutes"] == 0
    assert out["ok_budget"] is True


def test_invalid_repo_fails_closed(tmp_path: Path, capsys):
    code = cycle_end.main(
        ["--repo", "not-a-repo", "--issue", "1", "--dir", str(tmp_path)]
    )
    assert code == 1
    out = _payload(capsys)
    assert out["ok"] is False
    assert "owner/name" in out["error"]


def test_malformed_start_file_fails_closed(tmp_path: Path, capsys):
    path = tmp_path / "owner__name__2.json"
    path.write_text("not-json\n", encoding="utf-8")
    code = cycle_end.main(
        ["--repo", "owner/name", "--issue", "2", "--dir", str(tmp_path)]
    )
    assert code == 1
    out = _payload(capsys)
    assert out["ok"] is False
    assert out["path"] == str(path)
