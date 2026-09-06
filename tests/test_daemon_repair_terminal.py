"""A repair-only cycle must retain its outcome without another factory pass."""

import pytest
from lokay.proc.summarize_daemon_cycle import summarize


@pytest.mark.parametrize("repair,health", [
    ({"ok": False, "error": "validation timed out"}, "self_repair_failed"),
    ({"ok": True, "restart_required": True}, "self_repair_restart_required"),
])
def test_repair_route_has_terminal_without_factory(repair, health):
    result = summarize(lokay_node={}, repair=repair, selected={"route": "repair"})
    assert result["ok"] is True
    assert result["result"]["ok"] is False
    assert result["result"]["health"] == health
    assert result["result"]["self_repair"] == repair


@pytest.mark.parametrize("failed", [False, True])
def test_native_repair_cycle_never_enters_factory(tmp_path, failed):
    from test_issue_triage_fala import base_effector
    from test_implementation_selection_fala import run_graph

    body = base_effector(
        """if a == 'select_repair_route': v['route'] = 'repair'
if a == 'recovery_run_self_repair':
    if FAILED: raise RuntimeError('validation timed out')
    v.update(restart_required=True)
if a == 'recovery_factory': raise AssertionError('second repair must not start')
if a == 'summarize_daemon_cycle':
    from lokay.organ.recovery import handle_recovery
    from lokay.organ.common import _conduction_values
    v = handle_recovery(a, {}, _conduction_values(m), dict(cfg=[],live=[],repo='',issue_number=None,pr_number=None,repair_mode=False,branch=''))
""".replace('FAILED', repr(failed))
    )
    result = run_graph(tmp_path, body, 'repair-terminal', path_id='daemon_cycle')
    nodes = result['effector_results']
    assert nodes['recovery_factory']['status'] == 'skipped'
    assert nodes['summarize_daemon_cycle']['status'] == 'succeeded'
    outcome = nodes['summarize_daemon_cycle']['output']['values']['result']
    assert outcome['health'] == ('self_repair_failed' if failed else 'self_repair_restart_required')
