#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
uv run --offline python - <<'PY'
import sys
import tempfile
from lokay.check import local_ci
with tempfile.TemporaryDirectory() as root:
    for marker in ('collected 0 items', 'no tests ran', 'error: Failed to install', 'No solution found', 'ModuleNotFoundError', 'command not found', 'No such file or directory'):
        result = local_ci('sha', [[sys.executable, '-c', f'print({marker!r})']], root)
        assert result['result'] == 'red' and not result['failed'][0]['flaky'], result
    assert local_ci('sha', [[sys.executable, '-c', "print('1 passed')"]], root)['result'] == 'green'
    empty = local_ci('sha', [], root)
    assert empty['result'] == 'green' and empty['notes'][0]['log'] == 'no tests configured'
print('ci_not_run: 7 false greens blocked; real command and empty configuration OK')
PY
