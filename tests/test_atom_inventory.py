import json

import pytest


def test_inventory_reports_source_candidates_and_missing(tmp_path):
    from lokay.proc.atom_inventory import inventory

    package = tmp_path / 'graph.toml'
    package.write_text('''[[correlation_paths]]
id = "p"
[[correlation_paths.effectors]]
id = "a"
config = {atom = "inspect"}
[[correlation_paths.effectors]]
id = "b"
config = {atom = "missing"}
''')
    source = tmp_path / 'src'
    source.mkdir()
    (source / 'organ.py').write_text('def handle(atom):\n    if atom == "inspect":\n        return {}\n')
    report = inventory(package, source)
    assert report['scope'] == 'authored_not_expanded'
    assert report['nodes'][0]['sites'] == [{'file': 'organ.py', 'line': 2}]
    assert report['nodes'][0]['resolution'] == 'candidate'
    assert report['nodes'][1]['resolution'] == 'unresolved'
    assert report['nodes'][1]['sites'] == []


def test_missing_package_returns_json_error(tmp_path, capsys):
    from lokay.proc.atom_inventory import main

    assert main(['--package', str(tmp_path / 'missing')]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result['ok'] is False
    assert result['code'] == 'atom_inventory_invalid'


def test_missing_source_is_not_a_successful_empty_scan(tmp_path):
    from lokay.proc.atom_inventory import inventory

    package = tmp_path / 'graph.toml'
    package.write_text('correlation_paths = []')
    with pytest.raises(ValueError, match='source directory'):
        inventory(package, tmp_path / 'absent')
