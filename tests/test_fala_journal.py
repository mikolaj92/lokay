"""Hermetic tests for mill Fala sqlite rotation (tmp dir; no live mill)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lokay.compose import daemon_cycle
from lokay.fala_journal import rotate_mill_fala_journals
from lokay.proc import rotate_fala_journals


def _write_db(path: Path, *, size: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    return path


def test_rotate_sees_and_cuts_root_state_sqlite(tmp_path: Path):
    home = tmp_path / "home"
    db = home / ".lokay" / "fala" / "state.sqlite"
    _write_db(db, size=80)

    out = rotate_mill_fala_journals(home=home, min_bytes=50, keep=1)
    assert out["ok"] is True
    assert not db.exists()
    assert len(out["rotated"]) == 1
    assert Path(out["rotated"][0]["path"]) == db
    assert Path(out["rotated"][0]["archived"]).exists()
    assert out["rotated"][0]["before_bytes"] == 80


def test_rotate_every_fala_journal_including_nested(tmp_path: Path):
    home = tmp_path / "home"
    fala = home / ".lokay" / "fala"
    root = _write_db(fala / "state.sqlite", size=100)
    daemon = _write_db(fala / "daemon-cycle" / "state.sqlite", size=100)
    factory = _write_db(fala / "factory" / "state.sqlite", size=100)
    i2pr = _write_db(fala / "i2pr" / "mikolaj92__lokay__9" / "state.sqlite", size=100)
    slot = _write_db(fala / "factory-slot-0" / "state.sqlite", size=100)
    small = _write_db(fala / "product-entry" / "state.sqlite", size=10)
    wal = fala / "state.sqlite-wal"
    wal.write_bytes(b"wal")

    out = rotate_mill_fala_journals(home=home, min_bytes=50, keep=1)
    assert out["ok"] is True
    assert not root.exists()
    assert not daemon.exists()
    assert not factory.exists()
    assert not i2pr.exists()
    assert not slot.exists()
    assert small.exists()
    assert not wal.exists()
    archived = [row["archived"] for row in out["rotated"]]
    assert any(Path(path).name.startswith("state.sqlite.") for path in archived)
    assert len(out["rotated"]) == 5
    assert any(Path(row["path"]) == root for row in out["rotated"])


def test_rotate_fail_closed_when_cannot_cut(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    db = home / ".lokay" / "fala" / "state.sqlite"
    _write_db(db, size=80)

    def boom(self: Path, _target: Path) -> Path:
        raise OSError("read-only filesystem")

    monkeypatch.setattr(Path, "replace", boom)
    with pytest.raises(OSError, match="cannot cut over-cap Fala journal"):
        rotate_mill_fala_journals(home=home, min_bytes=50, keep=1)
    assert db.exists()


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
    db = home / ".lokay" / "fala" / "state.sqlite"
    _write_db(db, size=80)
    code = rotate_fala_journals.main(
        ["--lokay-home", str(home), "--min-bytes", "50", "--keep", "1"]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["ok"] is True
    assert payload["rotated"]
    assert not db.exists()


def test_rotate_cli_fail_closed_when_cannot_cut(tmp_path: Path, capsys, monkeypatch):
    home = tmp_path / "home"
    db = home / ".lokay" / "fala" / "state.sqlite"
    _write_db(db, size=80)

    def boom(self: Path, _target: Path) -> Path:
        raise OSError("read-only filesystem")

    monkeypatch.setattr(Path, "replace", boom)
    code = rotate_fala_journals.main(
        ["--lokay-home", str(home), "--min-bytes", "50", "--keep", "1"]
    )
    assert code != 0
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["ok"] is False
    assert db.exists()


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


def test_daemon_cycle_fail_closed_when_rotate_cannot_cut(monkeypatch, tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("mode: dry-run\n", encoding="utf-8")
    calls: list[str] = []

    def rotate():
        raise OSError("cannot cut over-cap Fala journal")

    def run_path(**_kwargs):
        calls.append("run")
        return {"ok": True, "health": "idle"}

    monkeypatch.setattr(daemon_cycle, "rotate_mill_fala_journals", rotate)
    monkeypatch.setattr(daemon_cycle, "run_path", run_path)
    monkeypatch.setattr(daemon_cycle, "trusted_fala_manifest", lambda: tmp_path / "pkg.toml")
    out = daemon_cycle.compose_daemon_cycle(config_path=str(cfg), pass_ceiling_seconds=5)
    assert calls == []
    assert out["ok"] is False
    assert out["reason"] == "journal_rotate"


def test_docs_do_not_claim_rotate_only_covers_daemon_cycle_factory():
    root = Path(__file__).resolve().parents[1]
    graph = (root / "docs" / "GRAPH.md").read_text(encoding="utf-8")
    working = (root / "docs" / "WORKING.md").read_text(encoding="utf-8")
    readme = (root / "README.md").read_text(encoding="utf-8")
    exclusive = (
        "~/.lokay/fala/{daemon-cycle,factory}",
        "under `~/.lokay/fala/daemon-cycle` and `factory`",
        "Live `fala/i2pr/` journals stay",
    )
    for text in (graph, working, readme):
        for phrase in exclusive:
            assert phrase not in text
    journal_row = next(
        line for line in graph.splitlines() if line.startswith("| mill Fala journals |")
    )
    assert "state.sqlite" in journal_row
    assert "~/.lokay/fala/" in journal_row
    assert "64 MiB" in readme
    assert "state.sqlite" in readme
