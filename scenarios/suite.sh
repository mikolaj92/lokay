#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
uv run --offline python - <<'PY'
import os
import re
import subprocess
import tempfile
from pathlib import Path

from lokay.config import load_repos

source = Path('scripts/check.sh').read_text()
names = re.search(r"scenarios='\n(.*?)\n'", source, re.S).group(1).split()
assert len(names) == len(set(names)), 'duplicate scenario'
assert {f'{name}.sh' for name in names} == {
    path.name for path in Path('scenarios').glob('*.sh')
    if path.name != 'darkfactory-canary.sh'
}, 'suite inventory is stale'
repo = next(row for row in load_repos(Path('repos.yaml')) if row['name'] == 'mikolaj92/lokay')
assert repo['test'] == ['bash', 'scripts/check.sh'], repo
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    (root / 'scripts').mkdir()
    (root / 'scripts/check.sh').write_text(source)
    (root / 'scenarios').mkdir()
    log = root / 'executed'
    env = dict(os.environ, SUITE_LOG=str(log))
    for name in names:
        (root / f'scenarios/{name}.sh').write_text(f'echo {name} >> "$SUITE_LOG"\n')
    def run():
        return subprocess.run(['bash', str(root / 'scripts/check.sh')], env=env,
                              capture_output=True, text=True)
    result = run()
    assert result.returncode == 0, result.stderr
    assert log.read_text().splitlines() == names
    assert f'{len(names)}/{len(names)}; errors=0' in result.stdout
    log.unlink()
    missing = root / 'scenarios/merge.sh'
    saved = missing.read_text()
    missing.unlink()
    result = run()
    assert result.returncode != 0 and 'missing scenario: merge' in result.stderr
    assert not log.exists(), 'missing file must fail before executing the suite'
    missing.write_text(saved)
    (root / 'scenarios/ci.sh').write_text('exit 17\n')
    result = run()
    assert result.returncode == 17, result
    assert log.read_text().splitlines() == names[:names.index('ci')]
print(f'suite: {len(names)} required; complete inventory, missing file and red failure OK')
PY
