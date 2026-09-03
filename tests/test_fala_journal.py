"""Hermetic tests for mill Fala journal maintenance (tmp dir; no live mill)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lokay.compose import daemon_cycle
from lokay.fala_journal import maintain_mill_fala_journals
from lokay.proc import rotate_fala_journals


def _write_db(path: Path, *, size: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    return path


def _capture_maintain(monkeypatch):
    calls: list[dict] = []

    def maintain(db_path, **kwargs):
        path = Path(db_path)
        calls.append({"db_path": path, **kwargs})
        return {
            "ok": True,
            "dry_run": False,
            "deleted_run_count": 1,
            "vacuumed": True,
        }

    monkeypatch.setattr("fala.maintain_journal", maintain)
    return calls


def test_over_cap_journal_uses_fala_maintain_not_rename(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    db = home / ".lokay" / "fala" / "state.sqlite"
    _write_db(db, size=80)
    wal = db.with_name("state.sqlite-wal")
    wal.write_bytes(b"wal")
    calls = _capture_maintain(monkeypatch)

    out = maintain_mill_fala_journals(home=home, min_bytes=50, keep=1)
    assert out["ok"] is True
    assert db.exists()
    assert wal.exists()
    assert db.read_bytes() == b"x" * 80
    assert len(out["maintained"]) == 1
    assert Path(out["maintained"][0]["path"]) == db
    assert out["maintained"][0]["before_bytes"] == 80
    assert calls == [
        {
            "db_path": db,
            "older_than_days": 0,
            "keep_last": 1,
            "vacuum": True,
            "dry_run": False,
        }
    ]
    assert wal.exists()
    assert list(db.parent.glob("state.sqlite.*")) == []


def test_maintain_every_fala_journal_including_nested(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    fala = home / ".lokay" / "fala"
    root = _write_db(fala / "state.sqlite", size=100)
    daemon = _write_db(fala / "daemon-cycle" / "state.sqlite", size=100)
    factory = _write_db(fala / "factory" / "state.sqlite", size=100)
    i2pr = _write_db(fala / "i2pr" / "mikolaj92__lokay__9" / "state.sqlite", size=100)
    slot = _write_db(fala / "factory-slot-0" / "state.sqlite", size=100)
    small = _write_db(fala / "product-entry" / "state.sqlite", size=10)
    calls = _capture_maintain(monkeypatch)

    out = maintain_mill_fala_journals(home=home, min_bytes=50, keep=1)
    assert out["ok"] is True
    assert small.exists()
    maintained = {Path(row["path"]) for row in out["maintained"]}
    assert maintained == {root, daemon, factory, i2pr, slot}
    assert small not in maintained
    assert {call["db_path"] for call in calls} == maintained
    assert all(path.exists() for path in maintained)


def test_busy_journal_is_skipped_so_live_children_do_not_block_the_mill(
    tmp_path: Path, monkeypatch
):
    home = tmp_path / "home"
    live = home / ".lokay" / "fala" / "i2pr" / "mikolaj92__lokay__9" / "state.sqlite"
    idle = home / ".lokay" / "fala" / "factory" / "state.sqlite"
    _write_db(live, size=80)
    _write_db(idle, size=80)

    def maintain(db_path, **kwargs):
        if Path(db_path) == live:
            raise RuntimeError("database is locked")
        return {"ok": True, "deleted_run_count": 1, "vacuumed": True}

    monkeypatch.setattr("fala.maintain_journal", maintain)
    out = maintain_mill_fala_journals(home=home, min_bytes=50, keep=1)
    assert out["ok"] is True
    assert live.exists() and idle.exists()
    assert [Path(row["path"]) for row in out["maintained"]] == [idle]


def test_maintain_fail_closed_when_fala_rejects(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    db = home / ".lokay" / "fala" / "state.sqlite"
    _write_db(db, size=80)

    def boom(_db_path, **_kwargs):
        raise RuntimeError("fala.maintain_journal failed")

    monkeypatch.setattr("fala.maintain_journal", boom)
    with pytest.raises(RuntimeError, match="maintain_journal"):
        maintain_mill_fala_journals(home=home, min_bytes=50, keep=1)
    assert db.exists()


def test_pytest_without_home_does_not_touch_operator_mill(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "tests/test_fala_journal.py::probe")
    monkeypatch.setenv("HOME", str(tmp_path / "operator"))
    db = tmp_path / "operator" / ".lokay" / "fala" / "daemon-cycle" / "state.sqlite"
    _write_db(db, size=200)
    called = []
    monkeypatch.setattr(
        "fala.maintain_journal",
        lambda *args, **kwargs: called.append((args, kwargs)) or {"ok": True},
    )
    out = maintain_mill_fala_journals(min_bytes=1)
    assert out["reason"] == "pytest"
    assert db.exists()
    assert called == []


def test_rotate_cli_uses_lokay_home(tmp_path: Path, capsys, monkeypatch):
    home = tmp_path / "home"
    db = home / ".lokay" / "fala" / "state.sqlite"
    _write_db(db, size=80)
    calls = _capture_maintain(monkeypatch)
    code = rotate_fala_journals.main(
        ["--lokay-home", str(home), "--min-bytes", "50", "--keep", "1"]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["ok"] is True
    assert payload["maintained"]
    assert db.exists()
    assert calls and calls[0]["db_path"] == db


def test_rotate_cli_fail_closed_when_fala_rejects(tmp_path: Path, capsys, monkeypatch):
    home = tmp_path / "home"
    db = home / ".lokay" / "fala" / "state.sqlite"
    _write_db(db, size=80)

    def boom(_db_path, **_kwargs):
        raise RuntimeError("fala.maintain_journal failed")

    monkeypatch.setattr("fala.maintain_journal", boom)
    code = rotate_fala_journals.main(
        ["--lokay-home", str(home), "--min-bytes", "50", "--keep", "1"]
    )
    assert code != 0
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["ok"] is False
    assert db.exists()


def test_daemon_cycle_maintains_before_run_path(monkeypatch, tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("mode: dry-run\n", encoding="utf-8")
    calls: list[str] = []

    def maintain():
        calls.append("maintain")
        return {"ok": True, "maintained": []}

    def run_path(**_kwargs):
        calls.append("run")
        return {"ok": True, "health": "idle"}

    monkeypatch.setattr(daemon_cycle, "maintain_mill_fala_journals", maintain)
    monkeypatch.setattr(daemon_cycle, "run_path", run_path)
    monkeypatch.setattr(daemon_cycle, "trusted_fala_manifest", lambda: tmp_path / "pkg.toml")
    out = daemon_cycle.compose_daemon_cycle(config_path=str(cfg), pass_ceiling_seconds=5)
    assert calls == ["maintain", "run"]
    assert out["ok"] is True


def test_daemon_cycle_fail_closed_when_maintain_cannot_run(monkeypatch, tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("mode: dry-run\n", encoding="utf-8")
    calls: list[str] = []

    def maintain():
        raise RuntimeError("fala.maintain_journal failed")

    def run_path(**_kwargs):
        calls.append("run")
        return {"ok": True, "health": "idle"}

    monkeypatch.setattr(daemon_cycle, "maintain_mill_fala_journals", maintain)
    monkeypatch.setattr(daemon_cycle, "run_path", run_path)
    monkeypatch.setattr(daemon_cycle, "trusted_fala_manifest", lambda: tmp_path / "pkg.toml")
    out = daemon_cycle.compose_daemon_cycle(config_path=str(cfg), pass_ceiling_seconds=5)
    assert calls == []
    assert out["ok"] is False
    assert out["reason"] == "journal_rotate"


def test_lokay_does_not_edit_sqlite_sidecars_directly():
    src = (Path(__file__).resolve().parents[1] / "src" / "lokay" / "fala_journal.py").read_text(
        encoding="utf-8"
    )
    assert "maintain_journal" in src
    assert ".replace(" not in src
    assert "unlink(" not in src
    assert "-wal" not in src
    assert "-shm" not in src


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
    assert "maintain_journal" in journal_row
    assert "cannot be cut" not in journal_row
    assert "maintain_journal" in readme
    assert "cannot be cut" not in readme
    assert "maintain_journal" in working



def test_created_zombie_runs_are_finalized_and_reclaimed(tmp_path: Path, monkeypatch):
    """SIGKILL after upsert_run leaves status=created. Maintain must reclaim them."""
    home = tmp_path / "home"
    db = _write_db(home / ".lokay" / "fala" / "daemon-entry" / "state.sqlite", size=80)
    i2pr = _write_db(
        home / ".lokay" / "fala" / "i2pr" / "mikolaj92__lokay__9" / "state.sqlite",
        size=80,
    )
    calls: list[tuple[str, str]] = []

    def list_runs(db_path, **_kwargs):
        path = Path(db_path)
        if path == db:
            return [
                {"id": "lokay-old-1", "status": "created"},
                {"id": "lokay-old-2", "status": "created"},
                {"id": "lokay-done", "status": "completed"},
            ]
        return [{"id": "lokay-live", "status": "created"}]

    def finalize_run(db_path, *, run_id, status, reason=None):
        calls.append(("finalize", run_id))
        assert status == "timed_out"
        assert Path(db_path) == db

    def delete_terminal_run(db_path, run_id):
        calls.append(("delete", run_id))
        assert Path(db_path) == db
        return {"ok": True}

    maintain_calls = _capture_maintain(monkeypatch)
    monkeypatch.setattr("fala.list_runs", list_runs)
    monkeypatch.setattr("fala.finalize_run", finalize_run)
    monkeypatch.setattr("fala.delete_terminal_run", delete_terminal_run)

    out = maintain_mill_fala_journals(home=home, min_bytes=50, keep=1)
    assert out["ok"] is True
    assert {Path(row["path"]) for row in out["maintained"]} == {db, i2pr}
    heartbeat = next(row for row in out["maintained"] if Path(row["path"]) == db)
    assert heartbeat["reclaimed_created"] == 2
    assert calls == [
        ("finalize", "lokay-old-1"),
        ("delete", "lokay-old-1"),
        ("finalize", "lokay-old-2"),
        ("delete", "lokay-old-2"),
    ]
    assert {call["db_path"] for call in maintain_calls} == {db, i2pr}


def test_invalid_status_journal_does_not_fail_the_mill(tmp_path: Path, monkeypatch):
    """Corrupt process/run status must not abort heartbeat journal maintain."""
    home = tmp_path / "home"
    db = _write_db(home / ".lokay" / "fala" / "daemon-cycle" / "state.sqlite", size=80)

    def boom(_db_path, **_kwargs):
        raise RuntimeError("fala read: row has an invalid status")

    monkeypatch.setattr("fala.list_runs", boom)
    calls = _capture_maintain(monkeypatch)
    out = maintain_mill_fala_journals(home=home, min_bytes=50, keep=1)
    assert out["ok"] is True
    assert db.exists()
    assert [Path(row["path"]) for row in out["maintained"]] == [db]
    assert calls and calls[0]["db_path"] == db


def test_created_reclaim_is_capped_per_journal(tmp_path: Path, monkeypatch):
    """Hundreds of created leftovers drain across ticks, not in one 180s maintain."""
    home = tmp_path / "home"
    db = _write_db(home / ".lokay" / "fala" / "daemon-entry" / "state.sqlite", size=80)
    calls: list[str] = []

    def list_runs(_db_path, **_kwargs):
        return [{"id": f"lokay-old-{i}", "status": "created"} for i in range(200)]

    def finalize_run(_db_path, *, run_id, status, reason=None):
        calls.append(run_id)

    def delete_terminal_run(_db_path, run_id):
        return {"ok": True}

    _capture_maintain(monkeypatch)
    monkeypatch.setattr("fala.list_runs", list_runs)
    monkeypatch.setattr("fala.finalize_run", finalize_run)
    monkeypatch.setattr("fala.delete_terminal_run", delete_terminal_run)

    out = maintain_mill_fala_journals(home=home, min_bytes=50, keep=1)
    assert out["ok"] is True
    heartbeat = next(row for row in out["maintained"] if Path(row["path"]) == db)
    assert heartbeat["reclaimed_created"] == 8
    assert calls == [f"lokay-old-{i}" for i in range(8)]


def test_missing_native_finalize_stops_reclaim_after_one_try(tmp_path: Path, monkeypatch):
    """Fala 0.7.31 has no native transition_run. Do not loop 822 AttributeErrors."""
    home = tmp_path / "home"
    db = _write_db(home / ".lokay" / "fala" / "daemon-entry" / "state.sqlite", size=80)
    calls: list[str] = []

    def list_runs(_db_path, **_kwargs):
        return [{"id": f"lokay-old-{i}", "status": "created"} for i in range(200)]

    def finalize_run(_db_path, *, run_id, status, reason=None):
        calls.append(run_id)
        raise AttributeError("module 'fala._native' has no attribute 'transition_run'")

    _capture_maintain(monkeypatch)
    monkeypatch.setattr("fala.list_runs", list_runs)
    monkeypatch.setattr("fala.finalize_run", finalize_run)
    monkeypatch.setattr("fala.delete_terminal_run", lambda *_a, **_k: {"ok": True})

    out = maintain_mill_fala_journals(home=home, min_bytes=50, keep=1)
    assert out["ok"] is True
    assert db.exists()
    assert calls == ["lokay-old-0"]

