#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
git init -q -b main "$tmp"
git -C "$tmp" config user.name t
git -C "$tmp" config user.email a@b.c
printf 'base\n' > "$tmp/tracked"
git -C "$tmp" add tracked
git -C "$tmp" commit -qm base
uv run python - "$tmp" <<'PY'
import subprocess
import sys
from pathlib import Path
from lokay.host_guard import guard

host = Path(sys.argv[1]).resolve()
(host / 'existing').write_text('keep')
def modify():
    (host / 'tracked').write_text('modified')
    (host / 'new').write_text('new')

with guard([host]) as result:
    modify()
assert result['changed'] is True, result
assert result['paths'] == [str(host)], result
assert (host / 'tracked').read_text() == 'base\n'
assert not (host / 'new').exists()
assert (host / 'existing').read_text() == 'keep'
with guard([host]) as unchanged:
    pass
assert unchanged == {'changed': False, 'paths': [], 'files': []}
# A dirty tracked file must retain the earlier edit, even on exception.
(host / 'tracked').write_text('earlier\n')
try:
    with guard([host]) as exceptional:
        modify()
        raise ValueError('step failed')
except ValueError:
    pass
assert exceptional['changed']
assert (host / 'tracked').read_text() == 'earlier\n'
assert not (host / 'new').exists()
assert (host / 'existing').read_text() == 'keep'
subprocess.run(['git', '-C', str(host), 'checkout', '--', 'tracked'], check=True)
(host / 'existing').unlink()
head = subprocess.check_output(['git', '-C', str(host), 'rev-parse', 'HEAD'])
with guard([host]) as committed:
    modify()
    subprocess.run(['git', '-C', str(host), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(host), 'commit', '-qm', 'step'], check=True)
assert committed['changed']
assert subprocess.check_output(['git', '-C', str(host), 'rev-parse', 'HEAD']) == head
assert (host / 'tracked').read_text() == 'base\n'
assert not (host / 'new').exists()
print('host_guard: restored tracked, new files, dirty baseline, exception, and HEAD')
PY
