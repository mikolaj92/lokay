#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
uv run --offline python - <<'PY'
import os
import re
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import yaml

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
    # The checkout cannot override a copied host configuration. Exercise the
    # actual loader twice, so a resumed check sees the repaired external file.
    external = root / 'repos.yaml'
    fixture = {'repos': [dict(repo), {
        'name': 'example/other', 'clone_path': '/unused',
        'test': ['true'], 'merge': 'off',
    }]}
    stale = ['bash', '-c', 'for s in scenarios/manifest.sh; do bash "$s" || exit 1; done']
    fixture['repos'][0]['test'] = stale
    external.write_text(yaml.safe_dump(fixture))
    with patch.dict(os.environ, LOKAY2_REPOS_FILE=str(external)):
        loaded = load_repos()
        assert loaded[0]['test'] == stale, 'external configuration was ignored'
        assert next(row for row in load_repos(Path('repos.yaml'))
                    if row['name'] == repo['name'])['test'] == repo['test']
        try:
            assert loaded[0]['test'] == repo['test'], 'host check differs from checkout gate'
        except AssertionError as error:
            assert str(error) == 'host check differs from checkout gate'
        else:
            raise AssertionError('stale host command escaped the gate')
        fixture['repos'][0]['test'] = repo['test']
        external.write_text(yaml.safe_dump(fixture))
        repaired = load_repos()
        assert repaired[0]['test'] == ['bash', 'scripts/check.sh']
        assert repaired[1] == loaded[1], 'repair changed another repo'
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
print(f'suite: {len(names)} required; external config red → repaired reload green, complete inventory, missing file and red failure OK')
PY
