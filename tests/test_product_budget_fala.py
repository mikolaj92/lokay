"""Native Fala proof for explicit serial product-pass slots."""

from test_issue_triage_fala import base_effector
from test_implementation_selection_fala import run_graph


def test_idle_first_pass_skips_remaining_slots(tmp_path):
    body = base_effector(
        """if a=='prepare_product_budget':v.update(route='run',budget=8)
if a.startswith('select_product_pass_slot_'):v.update(route='run' if a.endswith('_1') else 'empty')
if a.startswith('run_product_factory_pass_'):v.update(health='idle',idle=True,progress=0)
if a.startswith('run_product_leftover_closeout_'):v.update(labels_removed=False)
if a.startswith('apply_product_leftover_'):v['tick']={'health':'idle'}
if a.startswith('record_product_pass_'):v.update(slot=1,tick={'health':'idle'},results=[],total_progress=0,work_key=[0])
if a.startswith('classify_product_pass_'):v.update(route='idle')
if a.startswith('classify_product_plateau_'):v.update(route='idle')
if a.startswith('decide_product_pass_stop_'):v.update(stop_route='idle')
if a.startswith('finalize_product_pass_'):v.update(route='terminal',payload={'health':'idle'})
if a=='select_product_budget_result':v['result']={'health':'idle'}"""
    )
    result = run_graph(tmp_path, body, "product-idle", path_id="product_pass_budget")
    status = {k: v["status"] for k, v in result["effector_results"].items()}
    assert (
        status["run_product_factory_pass_1"] == "succeeded"
        and status["run_product_factory_pass_2"] == "skipped"
        and status["select_product_budget_result"] == "succeeded"
    )
