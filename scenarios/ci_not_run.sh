#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
uv run --offline python - <<'PY'
import sys
import tempfile
from pathlib import Path
from lokay.config import load_repos
from lokay.check import local_ci
with tempfile.TemporaryDirectory() as root:
    for marker in ('collected 0 items', 'no tests ran', 'error: Failed to install', 'No solution found', 'ModuleNotFoundError', 'command not found', 'No such file or directory', '', 'nothing to do', '0 passed', '1 passed; 0 passed'):
        result = local_ci('sha', [[sys.executable, '-c', f'print({marker!r})']], root)
        assert result['result'] == 'red' and not result['failed'][0]['flaky'], result
    assert local_ci('sha', [[sys.executable, '-c', "print('1 passed')"]], root)['result'] == 'green'
    empty = local_ci('sha', [], root)
    assert empty['result'] == 'green' and not empty['tested'] and empty['notes'][0]['log'] == 'no tests configured'
    root = Path(root).resolve()
    # Execute the configured Temida command against an isolated miniature checkout.
    for name in ('argus', 'dike', 'new_package'):
        package = root / 'packages' / name
        package.mkdir(parents=True)
        (package / 'pyproject.toml').touch()
    (root / 'tests').mkdir()
    (root / 'bin').mkdir()
    uv = root / 'bin' / 'uv'
    uv.write_text('#!/bin/sh\necho "pytest cwd=$PWD args=$*"\necho "1 passed"\n')
    uv.chmod(0o755)
    import os
    from unittest.mock import patch
    temida = next(repo for repo in load_repos(Path('repos.yaml')) if repo['name'] == 'mikolaj92/Temida')
    with patch.dict(os.environ, PATH=str(root / 'bin') + ':' + os.environ['PATH']):
        ci = local_ci('argus-head', [temida['test']], root)
    assert ci['result'] == 'green' and ci['tested'], ci
    assert set(ci['tested_cwds']) == {str(root), *(str(root / 'packages' / name) for name in ('argus', 'dike', 'new_package'))}, ci
    assert f'pytest cwd={root / "packages/argus"}' in ci['log'], ci
    assert f'pytest cwd={root} args=run --frozen pytest tests' in ci['log'], ci
print('ci_not_run: empty/no-op summaries rejected; Temida all packages + root tests executed; tested=false OK')
PY
