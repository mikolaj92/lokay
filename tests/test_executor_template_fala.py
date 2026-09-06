"""Native expansion conducts serial slots after skip and stops at the cap."""

import pytest
from test_issue_triage_fala import base_effector
from test_implementation_selection_fala import run_graph


@pytest.mark.parametrize("skip_first", [False, True])
def test_native_executor_slots_stop_after_one_launch(tmp_path, skip_first):
    body = base_effector(
        """from lokay.proc.select_executor_slot import select
from lokay.proc.classify_executor_row import classify
from lokay.proc.prepare_executor_rows import read_cursor
pd = Path(%r)
prepared = {'ok': True, 'cap': 1, 'budget': 1, 'spent': 0, 'slot_count': 8, 'pass_dir': str(pd)}
if a == 'prepare_executor_rows': v.update(prepared)
if a.startswith('select_executor_slot_'):
    slot = int(a.rsplit('_', 1)[1])
    v.update(select(prepared, read_cursor(str(pd)), slot=slot))
    (pd / ('selected-' + str(slot))).write_text(v['route'])
if a.startswith('run_executor_row_'):
    slot = int(a.rsplit('_', 1)[1])
    # This is a deterministic row fixture, not a coding worker.
    row = {'route': 'skip' if %r and slot == 1 else 'do', 'launched': None if %r and slot == 1 else 'started', 'leftover': 1, 'leftover_issues': [{'repo': 'o/r', 'issue': 3}]}
    (pd / ('row-' + str(slot))).write_text(json.dumps(row))
    v.update(result=row)
if a.startswith('classify_executor_row_'):
    slot = int(a.rsplit('_', 1)[1])
    route = (pd / ('selected-' + str(slot))).read_text()
    row = json.loads((pd / ('row-' + str(slot))).read_text()) if route == 'run' else {}
    v.update(classify({'route': route, 'slot': slot}, row, prepared=prepared))
""" % (str(tmp_path), skip_first, skip_first)
    )
    result = run_graph(tmp_path, body, "executor-native", path_id="executor_rows")
    statuses = {k: v["status"] for k, v in result["effector_results"].items()}
    assert statuses["run_executor_row_1"] == "succeeded"
    assert statuses["run_executor_row_2"] == ("succeeded" if skip_first else "skipped")
    assert statuses["run_executor_row_3"] == "skipped"
    assert statuses["select_executor_result"] == "succeeded"
