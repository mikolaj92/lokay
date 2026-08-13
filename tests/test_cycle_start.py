"""Hermetic tests for lokay-cycle-start (tmp dir; no Fala / GitHub)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from lokay.proc import cycle_start


def _payload(capsys) -> dict:
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def test_writes_receipt_under_dir(tmp_path: Path, capsys):
    code = cycle_start.main(
        ["--repo", "owner/name", "--issue", "42", "--dir", str(tmp_path)]
    )
    assert code == 0
    out = _payload(capsys)
    path = tmp_path / "owner__name__42.json"
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data == {"repo": "owner/name", "issue": 42, "started_ts": data["started_ts"]}
    assert out["ok"] is True
    assert out["repo"] == "owner/name"
    assert out["issue"] == 42
    assert out["path"] == str(path)
    assert out["started_ts"] == data["started_ts"]
    parsed = datetime.fromisoformat(data["started_ts"].replace("Z", "+00:00"))
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timezone.utc.utcoffset(parsed)
    assert data["started_ts"].endswith("Z")


def test_creates_missing_dir(tmp_path: Path, capsys):
    dest = tmp_path / "nested" / "cycle"
    code = cycle_start.main(
        ["--repo", "acme/lib", "--issue", "7", "--dir", str(dest)]
    )
    assert code == 0
    out = _payload(capsys)
    path = dest / "acme__lib__7.json"
    assert path.is_file()
    assert out["ok"] is True
    assert json.loads(path.read_text(encoding="utf-8"))["issue"] == 7


def test_default_dir_is_home_lokay_cycle(tmp_path: Path, monkeypatch, capsys):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    code = cycle_start.main(["--repo", "a/b", "--issue", "1"])
    assert code == 0
    out = _payload(capsys)
    path = home / ".lokay" / "cycle" / "a__b__1.json"
    assert path.is_file()
    assert out["ok"] is True
    assert out["path"] == str(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["repo"] == "a/b"
    assert data["issue"] == 1


def test_overwrites_existing_receipt(tmp_path: Path, capsys):
    path = tmp_path / "owner__name__3.json"
    path.write_text('{"repo": "owner/name", "issue": 3, "started_ts": "old"}\n')
    code = cycle_start.main(
        ["--repo", "owner/name", "--issue", "3", "--dir", str(tmp_path)]
    )
    assert code == 0
    out = _payload(capsys)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["started_ts"] != "old"
    assert data["started_ts"] == out["started_ts"]
    assert data["started_ts"].endswith("Z")


def test_invalid_repo_fails_closed(tmp_path: Path, capsys):
    code = cycle_start.main(
        ["--repo", "not-a-repo", "--issue", "1", "--dir", str(tmp_path)]
    )
    assert code == 1
    out = _payload(capsys)
    assert out["ok"] is False
    assert "owner/name" in out["error"]
    assert list(tmp_path.iterdir()) == []


def test_non_positive_issue_fails_closed(tmp_path: Path, capsys):
    code = cycle_start.main(
        ["--repo", "owner/name", "--issue", "0", "--dir", str(tmp_path)]
    )
    assert code == 1
    out = _payload(capsys)
    assert out["ok"] is False
    assert "positive" in out["error"]
    assert list(tmp_path.iterdir()) == []
