"""self_repair owns named children. Gate and mill stay outside this graph."""

import ast
import tomllib
from pathlib import Path

from lokay.graph_run import find_default_package

ROOT = Path(__file__).resolve().parents[1]

_SELF_REPAIR_CHILDREN = (
    "self_repair_prepare",
    "self_repair_run_agent",
    "self_repair_commit",
    "self_repair_validate",
    "self_repair_push_main",
    "self_repair_activate",
    "self_repair_preflight",
    "self_repair_close",
    "summarize_self_repair",
)

_FOREIGN = (
    "last_pass_moving",
    "select_repair_route",
    "classify_last_pass_progress",
    "recovery_mill",
    "recovery_begin",
    "factory_pass",
)


def _path(path_id: str) -> dict:
    pkg = tomllib.loads(find_default_package().read_text(encoding="utf-8"))
    return next(p for p in pkg["correlation_paths"] if p["id"] == path_id)


def test_self_repair_names_each_child_as_its_own_node():
    ids = [node["id"] for node in _path("self_repair")["effectors"]]
    assert ids == list(_SELF_REPAIR_CHILDREN)
    assert not set(_FOREIGN) & set(ids)


def test_prepare_validate_activate_are_child_falas():
    authored = {p["id"] for p in tomllib.loads(
        find_default_package().read_text(encoding="utf-8")
    )["correlation_paths"]}
    assert "self_repair_prepare" in authored
    assert "self_repair_validate" in authored
    assert "self_repair_activate_execution" in authored

    prepare = (ROOT / "src/lokay/proc/self_repair_prepare_subflow.py").read_text()
    validate = (ROOT / "src/lokay/proc/self_repair_validate_subflow.py").read_text()
    activate = (ROOT / "src/lokay/proc/self_repair_activate_subflow.py").read_text()
    assert 'path_id="self_repair_prepare"' in prepare
    assert 'path_id="self_repair_validate"' in validate
    assert 'path_id="self_repair_activate_execution"' in activate


def test_leaf_procs_do_not_fold_gate_or_mill_or_siblings():
    leaves = {
        "self_repair_push_main": ROOT / "src/lokay/proc/self_repair_push_main.py",
        "self_repair_preflight": ROOT / "src/lokay/proc/self_repair_preflight.py",
        "self_repair_close": ROOT / "src/lokay/proc/self_repair_close.py",
    }
    banned = (
        "last_pass_moving",
        "select_repair_route",
        "recovery_mill",
        "compose_mill",
        "self_repair_activate",
        "run_self_repair",
    )
    for name, path in leaves.items():
        source = path.read_text(encoding="utf-8")
        for token in banned:
            if name == "self_repair_push_main" and token == "self_repair_activate":
                continue
            assert token not in source, f"{name} folds {token}"


def test_organ_wires_named_children_not_one_recovery_mill():
    source = (ROOT / "src/lokay/organ/self_repair.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    handlers = {
        node.comparators[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Compare)
        and isinstance(node.left, ast.Name)
        and node.left.id == "atom"
        and node.comparators
        and isinstance(node.comparators[0], ast.Constant)
        and isinstance(node.comparators[0].value, str)
    }
    assert handlers == set(_SELF_REPAIR_CHILDREN)
    assert "recovery_mill" not in source
    assert "last_pass_moving" not in source


def test_docs_name_each_self_repair_child_in_order():
    graph = (ROOT / "docs" / "GRAPH.md").read_text(encoding="utf-8")
    section = graph.split("### `self_repair`")[1].split("### `issue_to_pr`")[0]
    for child in _SELF_REPAIR_CHILDREN[:-1]:
        assert child in section
    assert section.index("self_repair_commit") < section.index("self_repair_validate")
    assert "recovery_mill" not in section.split("```")[1]
    assert "last_pass_moving" not in section.split("```")[1]
