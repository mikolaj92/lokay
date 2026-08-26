"""Native Fala proofs: selected work skips hygiene and still writes a receipt."""

from test_implementation_selection_fala import run_graph
from test_issue_triage_fala import base_effector

HYGIENE = (
    "survey_prs",
    "survey_inbox",
    "survey_ready",
    "ready_hygiene",
    "plan_pass",
    "dispatch_triage",
    "resolve_conflicts",
    "closeout_prs",
    "reap_stale_implementing",
    "reap_over_budget",
    "refresh_occupancy",
    "reap_stale_worktrees",
)

WORK = (
    "queue_conflict",
    "dispatch_implement",
    "compute_health",
    "compact_state",
    "record_pass",
)


def _body(route: str, hygiene_mark: str, receipt_mark: str, dispatch_mark: str) -> str:
    hygiene_py = " ".join(repr(name) for name in HYGIENE)
    return base_effector(
        f"""if a=='classify_factory_idle':v.update(route='host')
if a=='factory_begin':v.update(pass_dir='/pass',planned=False)
if a=='select_implement':v.update(route={route!r})
if a=='dispatch_implement':Path({dispatch_mark!r}).write_text('dispatch')
if a=='record_pass':Path({receipt_mark!r}).write_text('receipt');v.update(result={{'ok':True,'health':'progress'}})
if a=='factory_pass_terminal':v.update(result={{'ok':True,'health':'progress'}})
if a in {{{hygiene_py}}}:Path({hygiene_mark!r}).write_text(a)"""
    )


def test_selected_tick_reaches_dispatch_and_receipt_without_hygiene(tmp_path):
    hygiene = str(tmp_path / "hygiene")
    receipt = str(tmp_path / "receipt")
    dispatch = str(tmp_path / "dispatch")
    result = run_graph(
        tmp_path,
        _body("selected", hygiene, receipt, dispatch),
        "factory-selected",
        path_id="factory_pass",
    )
    status = {name: row["status"] for name, row in result["effector_results"].items()}
    assert status["select_implement"] == "succeeded"
    assert status["dispatch_implement"] == "succeeded"
    assert status["record_pass"] == "succeeded"
    assert status["factory_pass_terminal"] == "succeeded"
    for name in HYGIENE:
        assert status[name] == "skipped", name
    assert tmp_path.joinpath("dispatch").is_file()
    assert tmp_path.joinpath("receipt").is_file()
    assert not tmp_path.joinpath("hygiene").exists()


def test_none_tick_runs_hygiene_and_skips_implement(tmp_path):
    hygiene = str(tmp_path / "hygiene")
    receipt = str(tmp_path / "receipt")
    dispatch = str(tmp_path / "dispatch")
    result = run_graph(
        tmp_path,
        _body("none", hygiene, receipt, dispatch),
        "factory-none",
        path_id="factory_pass",
    )
    status = {name: row["status"] for name, row in result["effector_results"].items()}
    assert status["select_implement"] == "succeeded"
    for name in WORK[:2]:
        assert status[name] == "skipped", name
    for name in HYGIENE:
        assert status[name] == "succeeded", name
    assert status["record_pass"] == "succeeded"
    assert tmp_path.joinpath("receipt").is_file()
    assert tmp_path.joinpath("hygiene").is_file()
    assert not tmp_path.joinpath("dispatch").exists()
