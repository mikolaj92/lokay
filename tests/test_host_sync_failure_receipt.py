"""Host maintenance failures are classified facts, not lost adapter errors."""
from lokay.fala_organ import organ_envelope
from lokay.organ.factory import handle_factory
from lokay.proc.gate_factory_begin_host import gate


def test_dirty_host_reason_survives_organ_and_gate():
    failure = {"ok": False, "_exit": 1, "reason": "host_behind",
               "health": "host_behind", "error": "refusing host-ff: checkout is dirty"}
    ctx = {"cfg": [], "live": ["--live"], "repo": "", "issue_number": None,
           "pr_number": None, "repair_mode": False, "branch": "",
           "run_atom_main": lambda *args: failure}
    result = handle_factory("host_ff", {}, {}, ctx)
    envelope = organ_envelope("host_ff", result)
    out = gate(envelope, live=True, checkout="")
    assert out["route"] == "blocked"
    assert out["reason"] == "host_behind"
    assert out["error"] == failure["error"]


def test_native_gate_retains_classified_sync_failure(tmp_path):
    from test_issue_triage_fala import base_effector, run_graph

    body = base_effector('''
from lokay.organ.common import _conduction_values
from lokay.proc.gate_factory_begin_host import gate
if a == 'host_ff':
    v.update(route='blocked', reason='host_behind', error='checkout is dirty')
if a == 'factory_begin_host_gate':
    v = gate(_conduction_values(m).get('host_ff') or {}, live=True, checkout='')
''')
    result = run_graph(tmp_path, body, "host-sync-blocked", path_id="factory_pass")
    nodes = result["effector_results"]
    assert nodes["factory_begin"]["status"] == "skipped"
    payload = nodes["factory_begin_host_gate"]["output"]["payload"]
    assert payload["reason"] == "host_behind"
    assert payload["error"] == "checkout is dirty"


def test_explicit_blocked_host_never_begins():
    assert gate({"ok": True, "route": "blocked", "reason": "host_behind"}, live=True, checkout="")["route"] == "blocked"
