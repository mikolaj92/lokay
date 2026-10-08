import json
from lokay.host_gate import stopped
from lokay.proc.gate_factory_begin_host import gate
from lokay.proc.select_repair_route import classify
from lokay.recovery_history import observe_run


def _host_stop():
    return stopped(gate({}, live=True, checkout=''))


def test_repeated_host_sync_stops_do_not_authorize_self_repair():
    history = [{**_host_stop(), 'kind': 'pass_receipt', 'ts': f'2026-10-06T16:00:0{n}Z', 'remaining': {'ready': 1}} for n in range(5, 0, -1)]
    out = classify(history[0], history=history)
    assert out['route'] == 'factory'
    assert out['reason'] == 'host_behind'


def test_host_sync_stop_does_not_fingerprint(tmp_path):
    state = tmp_path / 'state.jsonl'
    state.write_text(json.dumps({'kind': 'host_ff', 'ok': False, 'health': 'host_behind', 'error': 'host sync did not succeed'}) + '\n')
    out = observe_run(state_path=state, state_offset=0, lokay=_host_stop())
    assert out['fingerprint'] is None
