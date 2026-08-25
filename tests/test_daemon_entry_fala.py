"""Native Fala proofs for authored daemon entry routing."""

from test_implementation_selection_fala import run_graph
from test_issue_triage_fala import base_effector


def _body(route: str) -> str:
    return base_effector(
        f"""if a=='classify_daemon_preflight':v.update(route='{route}',preflight={{'ok':{route=='product'!s},'carrier_ok':{route!='carrier_failed'!s}}})
if a=='run_daemon_product_cycle':v.update(route='terminal',payload={{'ok':True,'health':'progress'}})
if a=='run_initial_self_repair':v.update(route='restart',repair={{'ok':True}})
if a=='daemon_entry_terminal':v['result']={{'ok':True,'health':'progress'}} if '{route}'=='product' else {{'ok':False,'health':'self_repair_restart_required' if '{route}'=='repair' else '{route}'}}"""
    )


def test_healthy_preflight_runs_only_product_cycle(tmp_path):
    result = run_graph(
        tmp_path, _body("product"), "daemon-product", path_id="daemon_entry"
    )
    status = {k: x["status"] for k, x in result["effector_results"].items()}
    assert (
        status["run_daemon_product_cycle"] == "succeeded"
        and status["run_initial_self_repair"] == "skipped"
    )


def test_recoverable_preflight_runs_only_initial_self_repair(tmp_path):
    result = run_graph(
        tmp_path, _body("repair"), "daemon-repair", path_id="daemon_entry"
    )
    status = {k: x["status"] for k, x in result["effector_results"].items()}
    assert (
        status["run_daemon_product_cycle"] == "skipped"
        and status["run_initial_self_repair"] == "succeeded"
    )


def test_overlap_runs_neither_product_nor_repair(tmp_path):
    result = run_graph(
        tmp_path, _body("overlap"), "daemon-overlap", path_id="daemon_entry"
    )
    status = {k: x["status"] for k, x in result["effector_results"].items()}
    assert (
        status["run_daemon_product_cycle"] == "skipped"
        and status["run_initial_self_repair"] == "skipped"
    )
