"""Native Fala proofs for direct product entry routing."""

from test_implementation_selection_fala import run_graph
from test_issue_triage_fala import base_effector


def _body(route: str) -> str:
    return base_effector(
        f"""if a=='classify_product_entry_preflight':v.update(route='{route}',preflight={{'ok':{route=='product'!s}}})
if a=='run_product_entry_budget':v.update(route='terminal',payload={{'ok':True,'health':'idle'}})
if a=='product_entry_terminal':v['result']={{'ok':True,'health':'idle'}} if '{route}'=='product' else {{'ok':False,'health':'preflight_failed'}}"""
    )


def test_healthy_entry_runs_one_product_budget(tmp_path):
    result = run_graph(
        tmp_path, _body("product"), "product-entry-ok", path_id="product_entry"
    )
    assert (
        result["effector_results"]["run_product_entry_budget"]["status"] == "succeeded"
    )


def test_failed_preflight_skips_product_budget(tmp_path):
    result = run_graph(
        tmp_path, _body("terminal"), "product-entry-failed", path_id="product_entry"
    )
    assert result["effector_results"]["run_product_entry_budget"]["status"] == "skipped"
