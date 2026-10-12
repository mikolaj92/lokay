#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
uv run --offline python - <<'PY'
import tempfile
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch
from lokay.build import build_code, _git
from lokay.run import run_process

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    _git(root, ['init', '-b', 'main'])
    _git(root, ['config', 'user.name', 'fixture'])
    _git(root, ['config', 'user.email', 'fixture@example.test'])
    (root / 'code.py').write_text('old\n')
    _git(root, ['add', '.']); _git(root, ['commit', '-m', 'base'])
    _git(root, ['update-ref', 'refs/remotes/origin/main', 'HEAD'])
    base = _git(root, ['rev-parse', 'HEAD'])
    for production in (False, True):
        _git(root, ['reset', '--hard', base])
        def pi(argv, **kwargs):
            if argv[0] != 'pi':
                return run_process(argv, **kwargs)
            (root / 'tests').mkdir(exist_ok=True)
            (root / 'tests/new.py').write_text('test\n')
            (root / 'test_new.py').write_text('test\n')
            (root / 'ui.spec.ts').write_text('test\n')
            _git(root, ['add', '.']); _git(root, ['commit', '-m', 'pi tests'])
            (root / 'ui.test.ts').write_text('untracked\n')
            if production:
                (root / 'code.py').write_text('new\n')
            return CompletedProcess(argv, 0, '', '')
        with patch('lokay.build.run_process', side_effect=pi):
            result = build_code(root, 'plan', 'fix', '', {})
        assert result['result'] == ('done' if production else 'failed'), result
        if not production:
            assert result['reason'] == 'tests_only', result
        assert _git(root, ['diff', '--name-only', 'origin/main..HEAD']) == ('code.py' if production else '')
        assert not (root / 'ui.test.ts').exists()
print('no_new_tests: committed, tracked, untracked; tests-only and production OK')
PY
