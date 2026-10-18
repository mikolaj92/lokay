#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
if grep -rnE '^(<<<<<<< |>>>>>>> |=======$)' src/ prompts/ sandbox/ scripts/; then
    exit 1
else
    [ "$?" -eq 1 ]
fi
sandbox=$(mktemp -d "$PWD/.lokay-check.XXXXXX")
trap 'rm -rf "$sandbox"' EXIT HUP INT TERM
export UV_CACHE_DIR="$sandbox/cache"
export UV_PROJECT_ENVIRONMENT="$PWD/.venv"
export UV_LOCKED=1
env -u UV_NO_SYNC -u UV_OFFLINE uv sync --locked --all-extras
.venv/bin/python -m compileall -q src
.venv/bin/python -I - <<'PY'
from pathlib import Path
import importlib
import pkgutil

import lokay
import yaml

expected = (Path.cwd() / 'src/lokay').resolve()
if lokay.__file__ is None or Path(lokay.__file__).resolve().parent != expected:
    raise SystemExit(f'wrong lokay location: {lokay.__file__}; expected {expected}')
def import_failed(name):
    raise ImportError(f'cannot import {name}')

for module in pkgutil.walk_packages(lokay.__path__, lokay.__name__ + '.', onerror=import_failed):
    importlib.import_module(module.name)
PY
mkdir -p "$sandbox/home" "$sandbox/tmp" "$sandbox/cache" "$sandbox/bin"
printf '%s\n' '#!/bin/sh' 'echo "unexpected external gh (blocked by local check)" >&2' 'exit 1' > "$sandbox/bin/gh"
chmod +x "$sandbox/bin/gh"
export HOME="$sandbox/home" TMPDIR="$sandbox/tmp" UV_CACHE_DIR="$sandbox/cache"
export UV_NO_SYNC=1 UV_PYTHON_DOWNLOADS=never UV_OFFLINE=1 PATH="$sandbox/bin:$PATH"
uv run python - <<'PY'
from dataclasses import replace
from pathlib import Path
import os
import tempfile

from lokay.checks import CheckInput, lockfile, secrets
from lokay.effects.pi import run_process
from lokay.effects.tests import check_uv_lock
from lokay.review import verdict
from subprocess import TimeoutExpired
from unittest.mock import patch as mock_patch

with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as directory:
    root = Path(directory)
    manifest = root / 'pyproject.toml'
    manifest.write_text('[project]\nname = "lock-probe"\nversion = "0.1.0"\nrequires-python = ">=3.11"\ndependencies = []\n')
    ci = {'sha': 'a' * 40, 'result': 'green', 'failed': []}
    candidate = CheckInput('probe', 1, ci['sha'], '', '', '', '', [], ci, root)
    missing = lockfile(candidate)
    assert missing.status == 'fail' and missing.findings[0].plik == 'uv.lock'
    generated = run_process(['uv', 'lock', '--offline'], cwd=root, timeout=60, env={**os.environ, 'UV_LOCKED': '0'})
    assert generated.returncode == 0
    assert lockfile(candidate).status == 'pass'
    manifest.write_text(manifest.read_text().replace('>=3.11', '>=3.12'))
    stale = lockfile(candidate)
    assert stale.status == 'fail' and candidate.sha in stale.reason
    assert verdict(candidate.sha, ci, [{'next': 'ok'}], (stale,))['result'] == 'fix'
    assert run_process(['uv', 'lock', '--offline'], cwd=root, timeout=60, env={**os.environ, 'UV_LOCKED': '0'}).returncode == 0
    updated_ci = {**ci, 'sha': 'b' * 40}
    repaired = replace(candidate, sha=updated_ci['sha'], ci=updated_ci)
    assert verdict(repaired.sha, updated_ci, [{'next': 'ok'}], (lockfile(repaired),))['result'] == 'merge'
    old = root / 'old.txt'
    new = root / 'new.txt'
    old.write_text('AKIAABCDEFGHIJKLMNOP\n' + '\n'.join(f'line {n}' for n in range(30)) + '\n')
    new.write_text(old.read_text().replace('line 2\n', 'AKIA1234567890ABCDEF\n').replace('line 25\n', '-----BEGIN OPENSSH PRIVATE KEY-----\n'))
    patch = run_process(['git', 'diff', '--no-index', '--unified=1', old.name, new.name], cwd=root, timeout=30)
    assert patch.returncode == 1
    scanned = replace(candidate, diff=patch.stdout)
    detected = secrets(scanned)
    assert detected.status == 'fail'
    assert [(item.plik, item.linia_od) for item in detected.findings] == [('new.txt', 4), ('new.txt', 27)]
    assert 'AKIA1234567890ABCDEF' not in str(detected)
    assert verdict(candidate.sha, ci, [{'next': 'ok'}], (detected,))['result'] == 'fix'
    new.write_text(old.read_text().replace('line 2\n', '-----BEGIN DOCUMENT-----\n'))
    patch = run_process(['git', 'diff', '--no-index', '--unified=1', old.name, new.name], cwd=root, timeout=30)
    assert secrets(replace(candidate, diff=patch.stdout)).status == 'pass'
    with mock_patch('lokay.effects.pi.run_process', side_effect=TimeoutExpired('uv', 60)):
        timed_out = lockfile(candidate)
        assert timed_out.status == 'fail'
        assert verdict(candidate.sha, ci, [{'next': 'ok'}], (timed_out,))['result'] == 'fix'
    with mock_patch('lokay.effects.pi.run_process', side_effect=OSError('tool missing')):
        assert check_uv_lock(root)[0] == 'fail'
    manifest.unlink()
    (root / 'uv.lock').unlink()
    assert lockfile(candidate).status == 'skip'
print('5 passed: lock drift, missing lock, repaired SHA, added secrets, benign diff')
PY
uv run lokay replay fixtures/replay/
uv run lokay replay fixtures/ticks/
