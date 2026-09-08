"""Age and broken Git pointers are not completion evidence (#1107)."""

import os

import pytest
from lokay.fala_journal import prune_stale_fala_journals, prune_stale_logs, prune_stale_tmp_dirs
from lokay.git_worktree import remove_worktree
from lokay.runner import Runner
from test_host_ff import _pair


@pytest.mark.parametrize('kind', ['journal', 'log', 'backup'])
def test_age_only_artifact_is_preserved(tmp_path, kind):
    if kind == 'journal':
        artifact = tmp_path / 'i2pr' / 'unfinished'
        artifact.mkdir(parents=True)
        payload = artifact / 'state.sqlite'
        payload.write_bytes(b'unfinished journal; no completion evidence')
        prune = prune_stale_fala_journals
    elif kind == 'log':
        artifact = tmp_path / 'lokay-20200101.log'
        artifact.write_text('only record of failed work')
        payload = artifact
        prune = prune_stale_logs
    else:
        artifact = tmp_path / 'deploy-backup-unpublished'
        artifact.mkdir()
        payload = artifact / 'recovery.patch'
        payload.write_text('unpublished work')
        prune = prune_stale_tmp_dirs
    before = payload.read_bytes()
    os.utime(artifact, (1, 1))
    result = prune(tmp_path, now=2_000_000_000)
    assert payload.read_bytes() == before
    assert result['pruned_count'] == 0
    assert result['reason'] == 'completion_evidence_required'


def test_orphan_with_uninspectable_git_is_not_deleted(tmp_path):
    _, clone = _pair(tmp_path)
    root = tmp_path / 'worktrees'
    wt = root / 'orphan'
    wt.mkdir(parents=True)
    (wt / '.git').write_text('gitdir: /does-not-exist/lokay-worktree\n')
    (wt / 'unpublished.py').write_text('important work')
    result = remove_worktree(Runner(), clone, wt, managed_root=root)
    assert result['removed'] is False
    assert (wt / 'unpublished.py').read_text() == 'important work'


def test_service_does_not_delete_logs_by_age():
    from pathlib import Path
    script = (Path(__file__).parents[1] / 'scripts/lokay-service.sh').read_text()
    assert '-mtime +7 -delete' not in script


def test_owned_clean_worktree_with_unpublished_commit_is_preserved(tmp_path):
    from test_host_ff import _git
    _, clone = _pair(tmp_path)
    root = tmp_path / 'worktrees'
    root.mkdir()
    wt = root / 'unpublished'
    _git(clone, 'worktree', 'add', '-b', 'ai/fix/7-unpublished', str(wt))
    (wt / 'unique.py').write_text('unpublished code')
    _git(wt, 'add', 'unique.py')
    _git(wt, 'commit', '-m', 'unpublished')
    result = remove_worktree(Runner(), clone, wt, managed_root=root)
    assert result['removed'] is False
    assert (wt / 'unique.py').read_text() == 'unpublished code'


def test_owned_clean_worktree_at_published_head_can_be_removed(tmp_path):
    from test_host_ff import _git
    _, clone = _pair(tmp_path)
    root = tmp_path / 'worktrees'
    root.mkdir()
    wt = root / 'delivered'
    _git(clone, 'worktree', 'add', '-b', 'ai/fix/8-delivered', str(wt))
    result = remove_worktree(Runner(), clone, wt, managed_root=root)
    assert result['removed'] is True
    assert not wt.exists()


def test_expired_recovery_archive_without_completion_is_retained(tmp_path):
    from lokay.proc.prune_preserved_worktree_archives import prune
    archive = tmp_path / 'owner__repo' / '.work.lokay-preserved'
    archive.mkdir(parents=True)
    evidence = archive / 'unpublished.patch'
    evidence.write_text('recovery evidence')
    os.utime(archive, (1, 1))
    result = prune(managed_root=tmp_path, live=True, now=2_000_000_000)
    assert evidence.read_text() == 'recovery evidence'
    assert result['pruned_count'] == 0
    assert result['retained'] == [str(archive)]


def test_wrapper_rollover_does_not_erase_unfinished_evidence(tmp_path):
    from lokay.fala_journal import wrapper_journal_dir
    root = tmp_path / '.lokay' / 'fala'
    paths = []
    for n in range(5):
        path = root / f'factory-pass-old-{n}'
        path.mkdir(parents=True)
        (path / 'state.sqlite').write_bytes(b'incomplete journal')
        os.utime(path, (n + 1, n + 1))
        paths.append(path)
    wrapper_journal_dir('factory_pass', home=tmp_path)
    assert all((p / 'state.sqlite').exists() for p in paths)


def test_journal_maintenance_does_not_finalize_active_runs(tmp_path, monkeypatch):
    from lokay.fala_journal import maintain_lokay_fala_journals
    db = tmp_path / '.lokay' / 'fala' / 'daemon-entry' / 'state.sqlite'
    db.parent.mkdir(parents=True)
    db.write_bytes(b'journal')
    calls = []
    monkeypatch.setattr('fala.list_runs', lambda *_a, **_k: [{'id': 'live', 'status': 'created'}])
    monkeypatch.setattr('fala.finalize_run', lambda *_a, **_k: calls.append('finalized'))
    monkeypatch.setattr('fala.delete_terminal_run', lambda *_a, **_k: calls.append('deleted'))
    def maintain(*args, **kwargs):
        calls.append(kwargs)
        return {'ok': True, 'deleted_run_count': 0, 'vacuumed': False}
    monkeypatch.setattr('fala.maintain_journal', maintain)
    maintain_lokay_fala_journals(home=tmp_path, min_bytes=1)
    assert 'finalized' not in calls
    assert 'deleted' not in calls
    assert calls[0]['dry_run'] is True


def test_self_repair_reclaim_does_not_invent_timeouts(tmp_path, monkeypatch):
    from lokay.fala_journal import reclaim_self_repair_incomplete_journals
    db = tmp_path / '.lokay' / 'fala' / 'self_repair_validate' / 'state.sqlite'
    db.parent.mkdir(parents=True)
    db.write_bytes(b'journal')
    calls = []
    monkeypatch.setattr('fala.list_runs', lambda *_a, **_k: [{'id': 'live', 'status': 'running'}])
    monkeypatch.setattr('fala.finalize_run', lambda *_a, **_k: calls.append('finalized'))
    out = reclaim_self_repair_incomplete_journals(home=tmp_path)
    assert calls == []
    assert out['reclaimed'] == []


def test_native_maintenance_preserves_terminal_and_incomplete_runs(tmp_path):
    import fala
    from fala.journal import ensure_journal, upsert_run_metadata
    from lokay.fala_journal import maintain_lokay_fala_journals
    db = tmp_path / '.lokay' / 'fala' / 'daemon-entry' / 'state.sqlite'
    ensure_journal(db)
    for ident, status in [('recover-me', 'created'), ('failure-evidence', 'failed'), ('done-evidence', 'completed')]:
        upsert_run_metadata(db, run_id=ident, status=status, metadata={'keep': ident})
    before = fala.list_runs(db)
    result = maintain_lokay_fala_journals(home=tmp_path, min_bytes=1, keep=0)
    after = fala.list_runs(db)
    assert after == before
    assert result['maintained'][0]['planned'] is True
    assert result['maintained'][0]['deleted_run_count'] == 0


def test_late_ignored_content_survives_registry_detach(tmp_path):
    from test_host_ff import _git
    _, clone = _pair(tmp_path)
    (clone / '.gitignore').write_text('*.secret\n')
    _git(clone, 'add', '.gitignore')
    _git(clone, 'commit', '-m', 'ignore private files')
    _git(clone, 'push', 'origin', 'main')
    root = tmp_path / 'worktrees'
    root.mkdir()
    wt = root / 'delivered'
    _git(clone, 'worktree', 'add', '-b', 'ai/fix/8-delivered', str(wt))
    archive = wt.with_name('.delivered.lokay-preserved')
    class LateWriter(Runner):
        def run(self, spec, *, live):
            if list(spec.argv)[1:3] == ['worktree', 'prune']:
                (archive / 'late.secret').write_text('not disposable')
            return super().run(spec, live=live)
    result = remove_worktree(LateWriter(), clone, wt, managed_root=root)
    assert result['reclaimed'] is False
    assert (archive / 'late.secret').read_text() == 'not disposable'
    assert result['preserved_path'] == str(archive)


def test_direct_archive_reclaim_requires_more_than_name_and_location(tmp_path):
    from lokay.git_worktree import reclaim_preserved_archive
    archive = tmp_path / '.work.lokay-preserved'
    archive.mkdir()
    (archive / 'valuable.patch').write_text('unpublished recovery')
    out = reclaim_preserved_archive(archive, managed_root=tmp_path)
    assert out['reclaimed'] is False
    assert (archive / 'valuable.patch').read_text() == 'unpublished recovery'


def test_empty_archive_can_be_reclaimed_without_content_loss(tmp_path):
    from lokay.git_worktree import reclaim_preserved_archive
    archive = tmp_path / '.empty.lokay-preserved'
    archive.mkdir()
    result = reclaim_preserved_archive(archive, managed_root=tmp_path)
    assert result['reclaimed'] is True
    assert not archive.exists()


def test_archive_reclaim_refuses_symlink_ancestor(tmp_path):
    from lokay.git_worktree import reclaim_preserved_archive
    foreign = tmp_path / 'foreign'
    foreign.mkdir()
    archive = foreign / '.empty.lokay-preserved'
    archive.mkdir()
    link = tmp_path / 'managed'
    link.symlink_to(foreign, target_is_directory=True)
    result = reclaim_preserved_archive(link / archive.name, managed_root=link)
    assert result['reclaimed'] is False
    assert archive.exists()
