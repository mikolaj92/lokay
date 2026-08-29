"""Native Fala proofs: parent conducts children, not leaves."""

import pytest

from test_implementation_selection_fala import run_graph
from test_issue_triage_fala import base_effector

CHILDREN = (
    "factory_begin",
    "reap_stale_worktrees",
    "select_self_repair_department",
    "run_self_repair_department",
    "select_issue_triage_department",
    "run_issue_triage_department",
    "select_executor_department",
    "run_executor_department",
    "select_pr_triage_department",
    "run_pr_triage_department",
    "select_pr_repair_department",
    "run_pr_repair_department",
    "record_pass",
    "factory_pass_terminal",
)

LEAVES = (
    "closeout_prs",
    "dispatch_implement",
    "select_implement",
    "queue_conflict",
    "survey_prs",
    "classify_factory_idle",
)


def _body(receipt_mark: str) -> str:
    kids = " ".join(repr(name) for name in CHILDREN)
    return base_effector(
        f"""if a=='factory_begin':v.update(pass_dir='/pass')
if a=='select_self_repair_department':v.update(route='skip',reason='last_pass_moved')
if a=='select_issue_triage_department':v.update(route='run')
if a=='select_executor_department':v.update(route='run')
if a=='select_pr_triage_department':v.update(route='run')
if a=='select_pr_repair_department':v.update(route='skip')
if a=='record_pass':Path({receipt_mark!r}).write_text('receipt');v.update(result={{'ok':True,'health':'progress'}})
if a=='factory_pass_terminal':v.update(result={{'ok':True,'health':'progress'}})
if a in {{{kids}}}:v.update(ok=True)"""
    )


def _require_fala_host():
    pytest.importorskip("fala")
    try:
        from fala._build import ensure_process_host_library

        ensure_process_host_library()
    except Exception as exc:
        pytest.skip(f"fala host unavailable: {exc}")


def test_parent_runs_department_children(tmp_path):
    _require_fala_host()
    receipt = str(tmp_path / "receipt")
    result = run_graph(
        tmp_path,
        _body(receipt),
        "factory-children",
        path_id="factory_pass",
    )
    status = {name: row["status"] for name, row in result["effector_results"].items()}
    for name in CHILDREN:
        assert status[name] == "succeeded", name
    for name in LEAVES:
        assert name not in status, name
    assert tmp_path.joinpath("receipt").is_file()


def test_failed_cleanup_still_picks_the_next_issue(tmp_path):
    """Throwing leftover-work-copy cleanup must not starve PRs or issues."""
    _require_fala_host()
    picked = str(tmp_path / "picked")
    receipt = str(tmp_path / "receipt")
    kids = " ".join(repr(name) for name in CHILDREN if name != "reap_stale_worktrees")
    body = base_effector(
        f"""if a=='factory_begin':v.update(pass_dir='/pass')
if a=='reap_stale_worktrees':raise RuntimeError('cleanup process.failed')
if a=='select_self_repair_department':v.update(route='skip',reason='last_pass_moved')
if a=='select_issue_triage_department':v.update(route='run')
if a=='run_issue_triage_department':Path({picked!r}).write_text('pr');v.update(route='do',launched='pr',leftover=1,leftover_issues=[{{'repo':'Temida/Temida','issue':4996}}])
if a=='select_executor_department':v.update(route='skip',reason='already_conducted')
if a=='select_pr_triage_department':v.update(route='run')
if a=='select_pr_repair_department':v.update(route='skip')
if a=='record_pass':Path({receipt!r}).write_text('receipt');v.update(result={{'ok':True,'outcome':'new_pr'}})
if a=='factory_pass_terminal':v.update(result={{'ok':True,'outcome':'new_pr'}})
if a in {{{kids}}}:v.update(ok=True)"""
    )
    result = run_graph(
        tmp_path,
        body,
        "factory-cleanup-fail",
        path_id="factory_pass",
    )
    status = {name: row["status"] for name, row in result["effector_results"].items()}
    assert status["reap_stale_worktrees"] == "failed"
    assert status["run_pr_triage_department"] == "succeeded"
    assert status["run_issue_triage_department"] == "succeeded"
    assert status["record_pass"] == "succeeded"
    assert status["factory_pass_terminal"] == "succeeded"
    assert tmp_path.joinpath("picked").read_text() == "pr"
    assert tmp_path.joinpath("receipt").is_file()
