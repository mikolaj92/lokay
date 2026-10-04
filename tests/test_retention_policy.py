"""Retention policy (t_2d81b9c3): execution data is consumable by age/cap."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from lokay import retention


def _old(path: Path, now: float, days: float) -> None:
    stamp = now - days * 86400
    os.utime(path, (stamp, stamp))


def test_wrapper_journals_beyond_keep_are_pruned_but_fresh_kept(tmp_path: Path):
    now = 2_000_000_000.0
    root = tmp_path / ".lokay" / "fala"
    root.mkdir(parents=True)
    for i in range(4):
        path = root / f"daemon-cycle-{i}"
        path.mkdir()
        _old(path, now, 30)
    fresh = root / "daemon-cycle-fresh"
    fresh.mkdir()
    os.utime(fresh, (now, now))

    out = retention.prune_wrapper_journals(root, keep=2, now=now)
    names = {p.name for p in root.iterdir()}
    assert fresh.name in names
    assert len(names) == 2  # keep window is total: newest + fresh allocation
    assert out["removed_count"] == 3


def test_wrapper_journal_dir_prunes_consumed_traces(tmp_path: Path):
    root = tmp_path / ".lokay" / "fala"
    root.mkdir(parents=True)
    for i in range(5):
        path = root / f"factory-pass-{i}"
        path.mkdir()
        (path / "state.sqlite").write_bytes(b"trace")
        stamp = time.time() - 40 * 86400
        os.utime(path, (stamp, stamp))
    from lokay.fala_journal import wrapper_journal_dir

    wrapper_journal_dir("factory_pass", home=tmp_path)
    remaining = sorted(p.name for p in root.iterdir() if p.is_dir())
    assert len(remaining) == 2  # newest consumed trace + the fresh allocation


def test_stale_terminal_journal_dir_is_removed(tmp_path: Path):
    now = 2_000_000_000.0
    import fala
    from fala.journal import ensure_journal

    jdir = tmp_path / "fala" / "coding-execution" / "mikolaj92__lokay__9"
    jdir.mkdir(parents=True)
    ensure_journal(jdir / "state.sqlite")
    _old(jdir, now, 30)

    out = retention.prune_stale_journal_dirs(tmp_path / "fala", max_age_days=14, now=now)
    assert out["removed_count"] == 1
    assert not jdir.exists()


def test_journal_dir_with_nonterminal_runs_is_retained(tmp_path: Path, monkeypatch):
    now = 2_000_000_000.0
    jdir = tmp_path / "fala" / "coding-execution" / "mikolaj92__lokay__9"
    jdir.mkdir(parents=True)
    (jdir / "state.sqlite").write_bytes(b"journal")
    _old(jdir, now, 30)
    monkeypatch.setattr(
        "fala.list_runs", lambda *_a, **_k: [{"id": "live", "status": "created"}]
    )

    out = retention.prune_stale_journal_dirs(tmp_path / "fala", max_age_days=14, now=now)
    assert out["removed_count"] == 0
    assert (jdir / "state.sqlite").exists()


def test_unreadable_journal_is_retained(tmp_path: Path):
    now = 2_000_000_000.0
    jdir = tmp_path / "fala" / "i2pr" / "mikolaj92__lokay__9"
    jdir.mkdir(parents=True)
    (jdir / "state.sqlite").write_bytes(b"not a database")
    _old(jdir, now, 30)

    out = retention.prune_stale_journal_dirs(tmp_path / "fala", max_age_days=14, now=now)
    assert out["removed_count"] == 0
    assert (jdir / "state.sqlite").exists()


def test_fresh_live_writer_is_never_removed(tmp_path: Path):
    import fala
    from fala.journal import ensure_journal

    jdir = tmp_path / "fala" / "executor_rows"
    jdir.mkdir(parents=True)
    ensure_journal(jdir / "state.sqlite")

    out = retention.prune_stale_journal_dirs(tmp_path / "fala", max_age_days=14)
    assert out["removed_count"] == 0
    assert jdir.exists()


def test_old_archives_removed_protected_state_never(tmp_path: Path):
    now = 2_000_000_000.0
    home = tmp_path
    old_archive = home / "fala-archive-daemon-cycles-20260928"
    old_archive.mkdir()
    _old(old_archive, now, 30)
    protected = home / "fail-digests"
    protected.mkdir()
    _old(protected, now, 30)

    out = retention.prune_stale_root_artifacts(home, max_age_days=14, now=now)
    assert not old_archive.exists()
    assert protected.exists()


def test_hard_cap_evicts_oldest_first_and_never_protected(tmp_path: Path):
    now = 2_000_000_000.0
    home = tmp_path
    root = home / "fala"
    root.mkdir()
    oldest = root / "daemon-cycle-old"
    oldest.mkdir()
    (oldest / "payload.bin").write_bytes(b"x" * 3000)
    _old(oldest, now, 40)
    newer = root / "daemon-cycle-new"
    newer.mkdir()
    (newer / "payload.bin").write_bytes(b"x" * 3000)
    _old(newer, now, 10)
    protected = home / "fail-digests"
    protected.mkdir()
    (protected / "digest.json").write_bytes(b"y" * 3000)
    _old(protected, now, 50)

    out = retention.enforce_hard_cap(home, cap_bytes=5000, now=now)
    assert not oldest.exists()
    assert not newer.exists()  # still over cap after the oldest batch
    assert protected.exists()  # protected state is never an eviction candidate
    assert out["after_bytes"] <= 5000


def test_hard_cap_noop_under_cap(tmp_path: Path):
    now = 2_000_000_000.0
    (tmp_path / "fala").mkdir()
    (tmp_path / "fala" / "state.sqlite").write_bytes(b"tiny")
    out = retention.enforce_hard_cap(tmp_path, cap_bytes=10 * 1024 * 1024, now=now)
    assert out["over_cap"] is False
    assert (tmp_path / "fala" / "state.sqlite").exists()


def test_config_retention_section():
    from lokay.config import load_config

    cfg_path = Path(__file__).resolve().parents[1] / "config.yaml"
    cfg = load_config(cfg_path)
    assert cfg.retention_max_age_days == 14
    assert cfg.retention_hard_cap_bytes == 10 * 1024 * 1024 * 1024
    assert cfg.retention_wrapper_keep == 2
    assert cfg.retention_journal_keep_last == 5


def test_retention_cli_filesystem_only(tmp_path: Path, capsys):
    from lokay.proc import run_retention

    now = time.time()
    root = tmp_path / ".lokay" / "fala"
    root.mkdir(parents=True)
    for i in range(4):
        path = root / f"daemon-cycle-{i}"
        path.mkdir()
        _old(path, now, 30)

    code = run_retention.main(
        ["--lokay-home", str(tmp_path), "--skip-sqlite", "--wrapper-keep", "2"]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["ok"] is True
    assert len(list(root.iterdir())) == 2


def test_maintenance_applies_age_policy_natively(tmp_path: Path):
    import fala
    from fala.journal import ensure_journal

    db = tmp_path / ".lokay" / "fala" / "executor_rows" / "state.sqlite"
    ensure_journal(db)
    import sqlite3

    conn = sqlite3.connect(db)
    for run_id, status, at in [
        ("old-done", "completed", "2020-01-01T00:00:00Z"),
        ("old-failed", "failed", "2020-01-02T00:00:00Z"),
        ("live-run", "created", "2020-01-03T00:00:00Z"),
    ]:
        conn.execute(
            "INSERT INTO runs (id,status,schema_version,metadata,created_at,updated_at,finished_at)"
            " VALUES (?,?,6,'{}',?,?,?)",
            (run_id, status, at, at, at if status != "created" else None),
        )
    conn.commit()
    conn.close()

    from lokay.fala_journal import maintain_lokay_fala_journals

    out = maintain_lokay_fala_journals(home=tmp_path, max_age_days=14, journal_keep_last=0)
    row = next(r for r in out["maintained"] if Path(r["path"]) == db)
    assert row["deleted_run_count"] == 2
    assert row["vacuumed"] is True
    remaining = {run["id"] for run in fala.list_runs(db)}
    assert remaining == {"live-run"}
