"""Hermetic tests for mill Fala sqlite rotation (tmp dir; no live mill)."""

from __future__ import annotations

import json
from pathlib import Path

from lokay.compose import daemon_cycle
from lokay.fala_journal import rotate_mill_fala_journals
from lokay.proc import rotate_fala_journals


def _write_db(path: Path, *, size: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    return path


def test_rotate_oversized_mill_journals_and_keep_i2pr(tmp_path: Path):
    home = tmp_path / "home"
    fala = home / ".lokay" / "fala"
    daemon = _write_db(fala / "daemon-cycle" / "state.sqlite", size=100)
    factory = _write_db(fala / "factory" / "state.sqlite", size=100)
    parent = _write_db(fala / "state.sqlite", size=10)
    i2pr = _write_db(fala / "i2pr" / "mikolaj92__lokay__9" / "state.sqlite", size=200)
    wal = fala / "daemon-cycle" / "state.sqlite-wal"
    wal.write_bytes(b"wal")

    out = rotate_mill_fala_journals(home=home, min_bytes=50, keep=1)
    assert out["ok"] is True
    assert not daemon.exists()
    assert not factory.exists()
    assert parent.exists()
    assert i2pr.exists()
    assert not wal.exists()
    archived = [row["archived"] for row in out["rotated"]]
    assert any(Path(path).name.startswith("state.sqlite.") for path in archived)
    assert len(out["rotated"]) == 2


def test_rotate_keeps_one_archive(tmp_path: Path):
    home = tmp_path / "home"
    db = home / ".lokay" / "fala" / "daemon-cycle" / "state.sqlite"
    _write_db(db, size=80)
    first = rotate_mill_fala_journals(home=home, min_bytes=50, keep=1)
    _write_db(db, size=80)
    second = rotate_mill_fala_journals(home=home, min_bytes=50, keep=1)
    archives = list((db.parent).glob("state.sqlite.*"))
    assert len(archives) == 1
    assert Path(second["rotated"][0]["archived"]).exists()
    assert not Path(first["rotated"][0]["archived"]).exists()


def test_pytest_without_home_does_not_touch_operator_mill(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "tests/test_fala_journal.py::probe")
    monkeypatch.setenv("HOME", str(tmp_path / "operator"))
    db = tmp_path / "operator" / ".lokay" / "fala" / "daemon-cycle" / "state.sqlite"
    _write_db(db, size=200)
    out = rotate_mill_fala_journals(min_bytes=1)
    assert out["reason"] == "pytest"
    assert db.exists()


def test_rotate_cli_uses_lokay_home(tmp_path: Path, capsys):
    home = tmp_path / "home"
    db = home / ".lokay" / "fala" / "factory" / "state.sqlite"
    _write_db(db, size=80)
    code = rotate_fala_journals.main(
        ["--lokay-home", str(home), "--min-bytes", "50", "--keep", "1"]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["ok"] is True
    assert payload["rotated"]
    assert not db.exists()


def test_daemon_cycle_rotates_before_run_path(monkeypatch, tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("mode: dry-run\n", encoding="utf-8")
    calls: list[str] = []

    def rotate():
        calls.append("rotate")
        return {"ok": True, "rotated": []}

    def run_path(**_kwargs):
        calls.append("run")
        return {"ok": True, "health": "idle"}

    monkeypatch.setattr(daemon_cycle, "rotate_mill_fala_journals", rotate)
    monkeypatch.setattr(daemon_cycle, "run_path", run_path)
    monkeypatch.setattr(daemon_cycle, "trusted_fala_manifest", lambda: tmp_path / "pkg.toml")
    out = daemon_cycle.compose_daemon_cycle(config_path=str(cfg), pass_ceiling_seconds=5)
    assert calls == ["rotate", "run"]
    assert out["ok"] is True
