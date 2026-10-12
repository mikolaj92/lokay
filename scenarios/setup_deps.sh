#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
uv run --offline python - <<'PY'
import os
import tempfile
from pathlib import Path
from unittest.mock import patch
from lokay.setup import prepare_dependencies
from lokay.config import load_repos
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    worktree = root / 'wt'; worktree.mkdir()
    bin = root / 'bin'; bin.mkdir()
    log = root / 'calls'
    for name in ('uv', 'npm'):
        fake = bin / name
        fake.write_text('#!/bin/sh\nprintf "%s:%s:%s\\n" "$PWD" "$(basename "$0")" "$*" >> "$CALLS"\nexit 1\n')
        fake.chmod(0o755)
    for directory, lock in (('.', 'uv.lock'), ('packages/a', 'uv.lock'), ('web', 'package-lock.json'), ('too/deep/ignored', 'uv.lock')):
        path = worktree / directory
        path.mkdir(parents=True, exist_ok=True); (path / lock).touch()
    repo = {'name': 'example/repo'}
    with patch.dict(os.environ, PATH=str(bin) + ':' + os.environ['PATH'], CALLS=str(log)), patch('lokay.state.RUNS', root / 'runs'):
        prepare_dependencies(worktree, repo, 1)
        calls = log.read_text().splitlines()
        assert len(calls) == 3 and not any('ignored' in call for call in calls), calls
        history = root / 'runs' / 'example' / 'repo' / '1' / 'rounds.md'
        from lokay.state import run_dir
        assert (run_dir(repo['name'], 1) / 'rounds.md').read_text().count('exit=1') == 3
        log.unlink()
        prepare_dependencies(worktree, {**repo, 'setup': ['sh', '-c', 'uv explicit']}, 1)
        assert len(log.read_text().splitlines()) == 1 and 'explicit' in log.read_text()
        log.unlink()
        prepare_dependencies(worktree, {**repo, 'setup': []}, 1)
        assert not log.exists()
    cfg = root / 'repos.yaml'
    cfg.write_text(f'repos:\n- name: example/repo\n  clone_path: {worktree}\n  test: []\n  merge: on\n  setup: [uv, sync, --frozen]\n')
    assert load_repos(cfg)[0]['setup'] == ['uv', 'sync', '--frozen']
print('setup_deps: depth, uv/npm, explicit/empty setup, failure logging and configuration OK')
PY
