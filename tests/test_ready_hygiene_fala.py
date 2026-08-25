"""Native Fala proof for one ready-hygiene catalog atom."""

from test_implementation_selection_fala import run_graph
from test_issue_triage_fala import base_effector


def test_ready_hygiene_is_one_catalog_atom(tmp_path):
    body = base_effector(
        """if a=='prepare_ready_hygiene':v.update(route='probe',repos=['o/r'])
if a=='ready_hygiene_catalog':v.update(cleaned_count=1)
if a=='update_ready_hygiene_stamp':v['result']={'cleaned_count':1}"""
    )
    result = run_graph(tmp_path, body, "ready-hygiene-catalog", path_id="ready_hygiene")
    order = [
        "prepare_ready_hygiene",
        "ready_hygiene_catalog",
        "update_ready_hygiene_stamp",
    ]
    statuses = result["effector_results"]
    assert all(statuses[name]["status"] == "succeeded" for name in order)
    assert not any(
        name.startswith("select_ready_hygiene_")
        or name.startswith("list_ready_hygiene_")
        or name.startswith("classify_ready_hygiene_")
        or name.startswith("record_ready_hygiene_")
        or name.startswith("remove_ready_hygiene_")
        or name.startswith("reduce_ready_hygiene")
        for name in statuses
    )
