"""Native Fala proof for explicit self-repair validation branches."""

import pytest

from test_issue_triage_fala import base_effector
from test_implementation_selection_fala import run_graph


def test_clean_candidate_without_untracked_paths(tmp_path):
    body = base_effector(
        """if a in {'read_self_repair_candidate_state','classify_self_repair_candidate_diff','validate_self_repair_identity_request','inspect_self_repair_candidate_identity','select_self_repair_identity_gate','verify_self_repair_candidate_identity','run_self_repair_tests'}:v.update(route='tests',worktree='/tmp/w',base_sha='',expected_subject='')
if a=='list_self_repair_untracked_paths':v.update(route='paths',paths=[],worktree='/tmp/w')
if a=='self_repair_untracked_catalog':v.update(route='tracked',worktree='/tmp/w',base_sha='')
if a.startswith('check_self_repair_tracked_'):v.update(route='valid',worktree='/tmp/w',base_sha='')
if a=='select_self_repair_committed_need':v.update(route='no_base',worktree='/tmp/w',base_sha='')
if a=='select_self_repair_committed_gate':v.update(route='valid',worktree='/tmp/w',base_sha='',expected_subject='')
if a=='recheck_self_repair_identity':v.update(validated_commit='',worktree='/tmp/w')
if a=='summarize_self_repair_validation':v['result']={'validated':True}"""
    )
    body = body.replace("if a=='list_self_repair_untracked_paths':", "if a=='run_self_repair_tests':v['route']='untracked'\nif a=='list_self_repair_untracked_paths':")
    result = run_graph(tmp_path, body, "validate-clean", path_id="self_repair_validate")
    status = {k: v["status"] for k, v in result["effector_results"].items()}
    assert (
        status["self_repair_untracked_catalog"] == "succeeded"
        and status["check_self_repair_tracked_committed"] == "skipped"
        and status["summarize_self_repair_validation"] == "succeeded"
    )


@pytest.mark.parametrize("adapter_failed", [False, True])
def test_failed_tests_skip_all_diff_validation(tmp_path, adapter_failed):
    body = base_effector(
        "v['route']='tests'\n"
        "if a=='select_self_repair_identity_gate':v['route']='identity'\n"
        "if a=='run_self_repair_tests':\n"
        "    v.update(ok=False,route='failed',test_returncode=124,test_timed_out=True)\n"
        f"    if {adapter_failed!r}:raise SystemExit(1)"
    )
    result = run_graph(tmp_path, body, "validate-failed", path_id="self_repair_validate")
    statuses = result["effector_results"]
    import tomllib
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    path = next(p for p in tomllib.loads((root / "fala/lokay.fala-package.toml").read_text())["correlation_paths"] if p["id"] == "self_repair_validate")
    names = [e["id"] for e in path["effectors"]]
    downstream = names[names.index("run_self_repair_tests") + 1:]
    assert all(statuses[name]["status"] == "skipped" for name in downstream), {
        name: statuses[name]["status"] for name in downstream
        if statuses[name]["status"] != "skipped"
    }
