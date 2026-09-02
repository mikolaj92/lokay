"""fala_organ and organ.* must not form a runtime import cycle."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "lokay"


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.append(node.module)
    return found


def test_organ_modules_do_not_import_fala_organ():
    organ = ROOT / "organ"
    offenders = []
    for path in organ.glob("*.py"):
        for name in _imports(path):
            if name == "lokay.fala_organ" or name.startswith("lokay.fala_organ."):
                offenders.append(f"{path.name}:{name}")
    assert offenders == []


def test_proc_modules_do_not_import_organ():
    proc = ROOT / "proc"
    offenders = []
    for path in proc.glob("*.py"):
        for name in _imports(path):
            if name == "lokay.organ" or name.startswith("lokay.organ."):
                offenders.append(f"{path.name}:{name}")
    assert offenders == []


def test_atom_runtime_and_execution_contracts_are_neutral():
    from lokay.atom_runtime import run_atom_main
    from lokay.execution_contracts import CATALOG_SLOT_COUNT

    assert CATALOG_SLOT_COUNT == 30
    assert callable(run_atom_main)
    runtime_imports = _imports(ROOT / "atom_runtime.py")
    contract_imports = _imports(ROOT / "execution_contracts.py")
    banned = {
        "lokay.fala_organ",
        "lokay.organ",
        "lokay.proc",
    }
    assert not any(
        name == banned_name or name.startswith(banned_name + ".")
        for name in runtime_imports + contract_imports
        for banned_name in banned
    )
