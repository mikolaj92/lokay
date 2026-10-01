import subprocess
from pathlib import Path
from lokay.organ.lanes import run_merge_tests


def test_remote_reviewed_commit_tested_without_touching_unpublished_work(tmp_path):
    def git(*args):
        return subprocess.check_output(['git', '-C', str(tmp_path), *args], text=True).strip()
    git('init', '-q')
    git('config', 'user.name', 'test')
    git('config', 'user.email', 'test@example.org')
    (tmp_path/'product').write_text('approved')
    git('add', '.'); git('commit', '-qm', 'approved')
    approved = git('rev-parse', 'HEAD')
    (tmp_path/'product').write_text('unpublished')
    git('commit', '-qam', 'local')
    local = git('rev-parse', 'HEAD')
    (tmp_path/'keep.txt').write_text('uncommitted work')
    before = git('status', '--porcelain')
    def tests(**kwargs):
        path = Path(kwargs['worktree'])
        assert path != tmp_path
        assert (path/'product').read_text() == 'approved'
        assert subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip() == approved
        return {'ok': True, 'tested': True, 'passed': True}
    result = run_merge_tests(tests, review={'decision': {'reviewed_head_sha': approved}}, worktree=str(tmp_path))
    assert result['ok'] is True
    assert result['tested_head_sha'] == approved
    assert git('rev-parse', 'HEAD') == local
    assert git('status', '--porcelain') == before
