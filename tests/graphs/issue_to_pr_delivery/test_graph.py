"""Branch checks use the authored delivery graph, not copied snapshots."""

import pytest
from support.graph_model import node_status_map, run_model
from test_issue_to_pr_fala import _package
from test_issue_triage_fala import base_effector, run_graph

_PATH_ID = "issue_to_pr_delivery"
_EFFECTORS = next(path for path in _package()["correlation_paths"] if path["id"] == _PATH_ID)["effectors"]
_MATCH = {
    "acceptance_repair_execution": {"ok": True},
    "assert_stamps_committed": {"route": "publish"},
    "coding_execution": {"route": "implemented"},
    "finalize_acceptance": {"route": "publish"},
    "finalize_local_tests": {"route": "repair_terminal"},
    "list_dirty_stamp_paths": {"route": "dirty"},
    "localize": {"route": "ready"},
    "resolve_implementation_issue": {"route": "open"},
    "select_local_test": {"route": "fail"},
    "select_publish_gate": {"route": "publish"},
    "verify_acceptance": {"ok": True, "route": "repair"},
    "worktree_add": {"route": "ready"},
}
_MISS = {node: {key: not value if isinstance(value, bool) else f"not-{value}" for key, value in values.items()}
         for node, values in _MATCH.items()}


def test_authored_dependencies_are_resolvable():
    nodes = {node["id"] for node in _EFFECTORS}
    assert len(nodes) == len(_EFFECTORS)
    for node in _EFFECTORS:
        assert set(node.get("conduction", [])).issubset(nodes)
        if node.get("when"):
            assert node["when"]["upstream"] in node["conduction"]


def test_model_match_and_miss_differ():
    assert run_model(_EFFECTORS, _MATCH) != run_model(_EFFECTORS, _MISS)


@pytest.mark.parametrize("values", [_MATCH, _MISS], ids=["match", "miss"])
def test_native_branches_skip_nonmatching_adapters(tmp_path, values):
    body = base_effector(f"v.update({values!r}.get(str(m.job).split(':')[-1], {{}}))")
    result = run_graph(tmp_path, body, "branches", path_id=_PATH_ID)
    assert result["run_status"] == "completed"
    assert node_status_map(result) == run_model(_EFFECTORS, values)
