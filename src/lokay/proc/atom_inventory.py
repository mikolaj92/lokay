"""Read-only authored atom/source inventory; candidates are not dispatch proof."""
from __future__ import annotations

import argparse
import ast
from pathlib import Path
import tomllib

from lokay.envelope import emit, ok, err


def inventory(package: Path, source: Path) -> dict:
    if not source.is_dir():
        raise ValueError('source directory does not exist')
    manifest = tomllib.loads(package.read_text(encoding='utf-8'))
    sites: dict[str, list[dict]] = {}
    for file in sorted(source.rglob('*.py')):
        tree = ast.parse(file.read_text(), filename=str(file))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            if not isinstance(node.left, ast.Name) or node.left.id != 'atom':
                continue
            if len(node.ops) != 1 or not isinstance(node.ops[0], (ast.Eq, ast.NotEq, ast.In, ast.NotIn)):
                continue
            for value in ast.walk(node.comparators[0]):
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    site = {'file': str(file.relative_to(source)), 'line': node.lineno}
                    if site not in sites.setdefault(value.value, []):
                        sites[value.value].append(site)
    rows = []
    for path in manifest.get('correlation_paths', []):
        for effector in path.get('effectors', []):
            atom = effector.get('config', {}).get('atom')
            candidates = sites.get(atom, []) if isinstance(atom, str) else []
            rows.append({'path': path['id'], 'effector': effector['id'], 'atom': atom,
                         'resolution': 'candidate' if candidates else 'unresolved',
                         'sites': candidates})
    return {'scope': 'authored_not_expanded', 'nodes': rows,
            'limitations': ['Static comparison sites, not proven ownership or transitive dependencies.',
                            'Templates and dynamic dispatch require separate resolution.']}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, default=Path('fala/lokay.fala-package.toml'))
    parser.add_argument('--source', type=Path, default=Path('src/lokay'))
    args = parser.parse_args(argv)
    try:
        report = inventory(args.package, args.source)
    except (OSError, ValueError, SyntaxError, KeyError, TypeError) as exc:
        emit(err(str(exc), code='atom_inventory_invalid'))
        return 1
    emit(ok(**report))
    return 0
