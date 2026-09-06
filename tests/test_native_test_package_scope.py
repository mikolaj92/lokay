"""Native test hosts must materialize the same bounded package as production."""

import importlib
import tomllib

import pytest


@pytest.mark.parametrize("module", ["test_issue_triage_fala", "test_implementation_selection_fala"])
def test_native_helper_materializes_only_requested_path(tmp_path, module):
    helper = importlib.import_module(module)
    helper.run_graph(tmp_path, helper.base_effector("if a == 'select_repair_route': v['route'] = 'factory'"), "bounded-package", path_id="daemon_cycle")
    package = tomllib.loads((tmp_path / "pkg.toml").read_text())
    assert [path["id"] for path in package["correlation_paths"]] == ["daemon_cycle"]
    assert package["runtime"]


def test_pr_outcome_materializes_only_requested_path(tmp_path):
    from test_pr_outcome_fala import test_red_checks_run_repair_node_not_review_or_merge

    test_red_checks_run_repair_node_not_review_or_merge(tmp_path)
    package = tomllib.loads((tmp_path / "pkg.toml").read_text())
    assert [path["id"] for path in package["correlation_paths"]] == ["pr_triage"]
