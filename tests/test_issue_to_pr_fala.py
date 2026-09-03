"""Proofs for the thin issue delivery parent and extracted children.

Native Fala host proofs run when the Mojo process host is available.
Authored conduction + when is always simulated from the package.
"""

from pathlib import Path

import pytest
import tomllib

from test_issue_triage_fala import base_effector, run_graph

ROOT = Path(__file__).resolve().parents[1]


def _package() -> dict:
    return tomllib.loads((ROOT / "fala/lokay.fala-package.toml").read_text())


def simulate_path(path_id: str, values: dict[str, dict]) -> dict[str, str]:
    """Apply authored conduction + when. Skipped upstream satisfies conduction."""
    path = next(p for p in _package()["correlation_paths"] if p["id"] == path_id)
    status: dict[str, str] = {}
    outputs: dict[str, dict] = {}

    def matches(when: dict) -> bool:
        if not when:
            return True
        upstream = str(when.get("upstream") or "")
        if status.get(upstream) != "succeeded":
            return False
        actual = outputs.get(upstream, {}).get(when.get("path"))
        return actual == when.get("equals")

    pending = list(path["effectors"])
    progressed = True
    while pending and progressed:
        progressed = False
        leftover = []
        for node in pending:
            deps = list(node.get("conduction") or [])
            if any(status.get(dep) not in {"succeeded", "skipped"} for dep in deps):
                leftover.append(node)
                continue
            name = str(node["id"])
            if matches(dict(node.get("when") or {})):
                status[name] = "succeeded"
                outputs[name] = dict(values.get(name) or {})
            else:
                status[name] = "skipped"
            progressed = True
        pending = leftover
    assert not pending, [node["id"] for node in pending]
    return status


def _fala_host_ready() -> bool:
    try:
        from fala._build import ensure_native

        ensure_native()
        return True
    except Exception:
        return False


def test_valid_implementation_skips_repair_then_publishes():
    st = simulate_path(
        "issue_to_pr_delivery",
        {
            "resolve_implementation_issue": {"route": "open"},
            "worktree_add": {"route": "ready"},
            "localize": {"route": "ready"},
            "coding_execution": {"route": "implemented"},
            "select_local_test": {"route": "pass"},
            "finalize_local_tests": {"route": "publish"},
        },
    )
    assert st["local_repair_execution"] == "skipped"
    assert st["push"] == "succeeded"
    assert st["pr_create"] == "succeeded"


def test_human_coding_skips_publish():
    st = simulate_path(
        "issue_to_pr_delivery",
        {
            "resolve_implementation_issue": {"route": "open"},
            "worktree_add": {"route": "ready"},
            "localize": {"route": "ready"},
            "coding_execution": {"route": "human"},
            "select_local_test": {"route": "skip"},
            "finalize_local_tests": {"route": "not_applicable"},
        },
    )
    assert st["test_local_execution"] == "skipped"
    assert st["select_local_test"] == "succeeded"
    assert st["local_repair_execution"] == "skipped"
    assert st["push"] == "skipped"
    assert st["pr_create"] == "skipped"
    assert st["summarize_issue_delivery"] == "succeeded"


def test_failed_coding_skips_relocalize_and_publish():
    st = simulate_path(
        "issue_to_pr_delivery",
        {
            "resolve_implementation_issue": {"route": "open"},
            "worktree_add": {"route": "ready"},
            "localize": {"route": "ready"},
            "coding_execution": {"route": "failed"},
            "select_local_test": {"route": "skip"},
            "finalize_local_tests": {"route": "not_applicable"},
        },
    )
    assert st["coding_execution"] == "succeeded"
    assert st["relocalize_off_goal"] == "skipped"
    assert st["assert_implementation_diff"] == "skipped"
    assert st["test_local_execution"] == "skipped"
    assert st["select_local_test"] == "succeeded"
    assert st["local_repair_execution"] == "skipped"
    assert st["push"] == "skipped"
    assert st["pr_create"] == "skipped"
    assert st["summarize_issue_delivery"] == "succeeded"


def test_skipped_select_local_test_is_a_miss_for_repair():
    """select_local_test always runs. skip is a real when miss, not a parent fail."""
    st = simulate_path(
        "issue_to_pr_delivery",
        {
            "resolve_implementation_issue": {"route": "open"},
            "worktree_add": {"route": "ready"},
            "localize": {"route": "ready"},
            "coding_execution": {"route": "failed"},
            "select_local_test": {"route": "skip"},
            "finalize_local_tests": {"route": "not_applicable"},
        },
    )
    assert st["select_local_test"] == "succeeded"
    assert st["local_repair_execution"] == "skipped"
    assert st["coding_repair_terminal"] == "skipped"
    assert st["assert_real_diff"] == "skipped"
    assert st["summarize_issue_delivery"] == "succeeded"


def test_red_test_runs_local_repair_then_terminal():
    st = simulate_path(
        "issue_to_pr_delivery",
        {
            "resolve_implementation_issue": {"route": "open"},
            "worktree_add": {"route": "ready"},
            "localize": {"route": "ready"},
            "coding_execution": {"route": "implemented"},
            "select_local_test": {"route": "fail"},
            "local_repair_execution": {"route": "terminal"},
            "finalize_local_tests": {"route": "repair_terminal"},
        },
    )
    assert st["local_repair_execution"] == "succeeded"
    assert st["coding_repair_terminal"] == "succeeded"
    assert st["push"] == "skipped"


def test_parent_gate_invokes_delivery_only_when_no_delivery_exists():
    st = simulate_path(
        "issue_to_pr",
        {
            "resolve_implementation_issue": {"route": "open"},
            "resolve_existing_delivery": {"route": "deliver"},
        },
    )
    assert st["issue_to_pr_subflow"] == "succeeded"
    assert st["close_existing_delivery"] == "skipped"
    assert st["issue_to_pr_no_effect"] == "skipped"


def test_parent_gate_closeout_skips_delivery_subflow():
    st = simulate_path(
        "issue_to_pr",
        {
            "resolve_implementation_issue": {"route": "open"},
            "resolve_existing_delivery": {"route": "closeout"},
        },
    )
    assert st["close_existing_delivery"] == "succeeded"
    assert st["issue_to_pr_subflow"] == "skipped"


def test_coding_execution_skips_retry_and_evidence():
    st = simulate_path(
        "coding_execution",
        {
            "validate_coding_result": {"route": "valid"},
            "select_coding_result": {
                "route": "implemented",
                "evidence_kind": "none",
            },
            "select_evidence_coding": {"route": "not_applicable"},
            "finalize_coding_result": {"route": "implemented"},
        },
    )
    assert st["coding_retry_agent"] == "skipped"
    assert st["evidence_coding_agent"] == "skipped"
    assert st["coding_execution_terminal"] == "succeeded"


def test_coding_execution_invalid_json_runs_one_retry():
    st = simulate_path(
        "coding_execution",
        {
            "validate_coding_result": {"route": "retry"},
            "validate_coding_retry": {"route": "valid"},
            "select_coding_result": {"route": "human", "evidence_kind": "none"},
            "select_evidence_coding": {"route": "not_applicable"},
            "finalize_coding_result": {"route": "human"},
        },
    )
    assert st["coding_retry_agent"] == "succeeded"
    assert st["coding_manual"] == "succeeded"


def test_coding_execution_runs_only_selected_collector():
    st = simulate_path(
        "coding_execution",
        {
            "validate_coding_result": {"route": "valid"},
            "select_coding_result": {
                "route": "evidence",
                "evidence_kind": "test_contract",
            },
            "validate_evidence_coding": {"route": "valid"},
            "select_evidence_coding": {"route": "human"},
            "finalize_coding_result": {"route": "human"},
        },
    )
    assert st["collect_coding_test_contract"] == "succeeded"
    assert st["collect_coding_issue_snapshot"] == "skipped"
    assert st["collect_coding_repo_structure"] == "skipped"
    assert st["collect_coding_localized_diff"] == "skipped"


def test_local_repair_invalid_json_is_terminal():
    st = simulate_path(
        "local_repair_execution",
        {
            "validate_repair_result": {"route": "retry"},
            "select_repair_result": {"route": "terminal"},
            "select_local_test_recheck": {"route": "not_applicable"},
        },
    )
    assert st["repair_agent"] == "succeeded"
    assert st["commit_repair"] == "skipped"
    assert st["test_local_recheck"] == "skipped"
    assert st["local_repair_terminal"] == "succeeded"


def test_missing_worktree_skips_coding_and_publish():
    st = simulate_path(
        "issue_to_pr_delivery",
        {
            "resolve_implementation_issue": {"route": "open"},
            "worktree_add": {"route": "missing"},
            "select_local_test": {"route": "skip"},
            "finalize_local_tests": {"route": "not_applicable"},
        },
    )
    assert st["worktree_add"] == "succeeded"
    assert st["plan_issue"] == "skipped"
    assert st["localize"] == "skipped"
    assert st["coding_execution"] == "skipped"
    assert st["pr_create"] == "skipped"
    assert st["summarize_issue_delivery"] == "succeeded"


def test_empty_localize_skips_coding_and_publish():
    st = simulate_path(
        "issue_to_pr_delivery",
        {
            "resolve_implementation_issue": {"route": "open"},
            "worktree_add": {"route": "ready"},
            "localize": {"route": "empty"},
            "select_local_test": {"route": "skip"},
            "finalize_local_tests": {"route": "not_applicable"},
        },
    )
    assert st["worktree_add"] == "succeeded"
    assert st["plan_issue"] == "succeeded"
    assert st["localize"] == "succeeded"
    assert st["coding_execution"] == "skipped"
    assert st["relocalize_off_goal"] == "skipped"
    assert st["pr_create"] == "skipped"
    assert st["summarize_issue_delivery"] == "succeeded"


def test_native_valid_implementation_skips_repair_then_publishes(tmp_path):
    if not _fala_host_ready():
        pytest.skip("Fala Mojo process host is not available")
    pushed = tmp_path / "push"
    wrong = tmp_path / "wrong"
    body = base_effector(
        """if a=='resolve_implementation_issue':v['route']='open'
if a=='worktree_add':v.update(route='ready')
if a=='localize':v.update(route='ready',paths=['src/x.py'])
if a=='coding_execution':v.update(route='implemented',decision={'verdict':'implemented'})
if a=='test_local_execution':v.update(tested=True)
if a=='select_local_test':v['route']='pass'
if a=='finalize_local_tests':v['route']='publish'
if a=='push':Path(%r).write_text('ran')
if a=='local_repair_execution':Path(%r).write_text(a)"""
        % (str(pushed), str(wrong))
    )
    result = run_graph(tmp_path, body, "implemented", path_id="issue_to_pr_delivery")
    st = {k: x["status"] for k, x in result["effector_results"].items()}
    assert st["local_repair_execution"] == "skipped"
    assert st["push"] == "succeeded" and pushed.exists() and not wrong.exists()


def test_native_failed_coding_skips_relocalize(tmp_path):
    if not _fala_host_ready():
        pytest.skip("Fala Mojo process host is not available")
    reloc = tmp_path / "reloc"
    body = base_effector(
        """if a=='resolve_implementation_issue':v['route']='open'
if a=='worktree_add':v.update(route='ready')
if a=='localize':v.update(route='ready',paths=['src/x.py'])
if a=='coding_execution':v.update(route='failed')
if a=='select_local_test':v['route']='skip'
if a=='finalize_local_tests':v['route']='not_applicable'
if a=='relocalize_off_goal':Path(%r).write_text(a)
if a=='local_repair_execution':Path(%r).write_text(a)"""
        % (str(reloc), str(tmp_path / "repair"))
    )
    result = run_graph(tmp_path, body, "coding-failed", path_id="issue_to_pr_delivery")
    st = {k: x["status"] for k, x in result["effector_results"].items()}
    assert st["coding_execution"] == "succeeded"
    assert st["relocalize_off_goal"] == "skipped"
    assert st["select_local_test"] == "succeeded"
    assert st["local_repair_execution"] == "skipped"
    assert st["pr_create"] == "skipped"
    assert st["summarize_issue_delivery"] == "succeeded"
    assert not reloc.exists()
    assert not (tmp_path / "repair").exists()
    assert "adapter_failed" not in str(result.get("error") or "")
    assert "condition_source_not_succeeded" not in str(result.get("error") or "")


def test_native_empty_localize_skips_coding_and_relocalize(tmp_path):
    """Empty localize skips coding; native when must skip relocalize, not throw."""
    if not _fala_host_ready():
        pytest.skip("Fala Mojo process host is not available")
    reloc = tmp_path / "reloc"
    body = base_effector(
        """if a=='resolve_implementation_issue':v['route']='open'
if a=='worktree_add':v.update(route='ready')
if a=='localize':v.update(route='empty',paths=[])
if a=='select_local_test':v['route']='skip'
if a=='finalize_local_tests':v['route']='not_applicable'
if a=='coding_execution':Path(%r).write_text(a)
if a=='relocalize_off_goal':Path(%r).write_text(a)"""
        % (str(tmp_path / "coding"), str(reloc))
    )
    result = run_graph(tmp_path, body, "localize-empty", path_id="issue_to_pr_delivery")
    st = {k: x["status"] for k, x in result["effector_results"].items()}
    assert st["localize"] == "succeeded"
    assert st["coding_execution"] == "skipped"
    assert st["relocalize_off_goal"] == "skipped"
    assert st["pr_create"] == "skipped"
    assert st["summarize_issue_delivery"] == "succeeded"
    assert not (tmp_path / "coding").exists()
    assert not reloc.exists()
    assert "adapter_failed" not in str(result.get("error") or "")
    assert "condition_source_not_succeeded" not in str(result.get("error") or "")

