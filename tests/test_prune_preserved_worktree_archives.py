"""TTL GC for `.lokay-preserved` archives — tmp dirs only."""

import os
import time
from pathlib import Path

from lokay.proc.prune_preserved_worktree_archives import (
    PRESERVED_ARCHIVE_TTL_SECONDS,
    list_expired_archives,
    prune,
)


def test_list_expired_only_quarantine_under_repo(tmp_path):
    repo = tmp_path / "mikolaj92__Temida"
    repo.mkdir()
    fresh = repo / ".ai__fix__1.lokay-preserved"
    fresh.mkdir()
    old = repo / ".ai__fix__2.lokay-preserved"
    old.mkdir()
    (repo / "ai__fix__3").mkdir()  # live worktree name — not an archive
    now = time.time()
    os.utime(fresh, (now - 10, now - 10))
    os.utime(old, (now - PRESERVED_ARCHIVE_TTL_SECONDS - 5, now - PRESERVED_ARCHIVE_TTL_SECONDS - 5))
    expired = list_expired_archives(tmp_path, now=now)
    assert expired == [old]


def test_prune_live_reclaims_expired_tmp_only(tmp_path):
    repo = tmp_path / "owner__repo"
    repo.mkdir()
    old = repo / ".corner.lokay-preserved"
    old.mkdir()
    (old / "blob").write_text("x\n", encoding="utf-8")
    now = time.time()
    os.utime(old, (now - PRESERVED_ARCHIVE_TTL_SECONDS - 1, now - PRESERVED_ARCHIVE_TTL_SECONDS - 1))
    out = prune(managed_root=tmp_path, live=True, now=now)
    assert out["ok"] is True
    assert out["pruned_count"] == 1
    assert not old.exists()


def test_prune_planned_does_not_delete(tmp_path):
    repo = tmp_path / "owner__repo"
    repo.mkdir()
    old = repo / ".corner.lokay-preserved"
    old.mkdir()
    now = time.time()
    os.utime(old, (now - PRESERVED_ARCHIVE_TTL_SECONDS - 1, now - PRESERVED_ARCHIVE_TTL_SECONDS - 1))
    out = prune(managed_root=tmp_path, live=False, now=now)
    assert out["planned"] is True
    assert out["candidate_count"] == 1
    assert out["pruned_count"] == 0
    assert old.exists()


def test_reclaim_refuses_non_archive_name(tmp_path):
    from lokay.git_worktree import reclaim_preserved_archive

    victim = tmp_path / "not-an-archive"
    victim.mkdir()
    out = reclaim_preserved_archive(victim, managed_root=tmp_path)
    assert out["ok"] is False
    assert victim.exists()


def test_prune_refuses_operator_lokay_under_pytest(monkeypatch, tmp_path):
    import lokay.proc.prune_preserved_worktree_archives as mod

    fake_home = tmp_path / "home"
    lokay = fake_home / ".lokay" / "worktrees"
    lokay.mkdir(parents=True)
    old = lokay / "owner__repo" / ".x.lokay-preserved"
    old.mkdir(parents=True)
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_prune_refuses (call)")
    monkeypatch.setattr(mod, "_is_operator_lokay_worktrees", lambda root: True)
    out = prune(managed_root=lokay, live=True)
    assert out.get("skipped") is True
    assert out["reason"] == "pytest_refuses_operator_lokay"
    assert old.exists()


def test_prune_bounds_expired_archives_to_authored_slots(tmp_path):
    from lokay.proc.stale_worktree_catalog import SLOTS

    repo = tmp_path / "owner__repo"
    repo.mkdir()
    now = time.time()
    archives = []
    for index in range(SLOTS + 2):
        archive = repo / f".{index}.lokay-preserved"
        archive.mkdir()
        os.utime(
            archive,
            (
                now - PRESERVED_ARCHIVE_TTL_SECONDS - 10,
                now - PRESERVED_ARCHIVE_TTL_SECONDS - 10,
            ),
        )
        archives.append(archive)

    assert len(list_expired_archives(tmp_path, now=now)) == SLOTS
    out = prune(managed_root=tmp_path, live=True, now=now)
    assert out["pruned_count"] == SLOTS
    assert sum(path.exists() for path in archives) == 2
