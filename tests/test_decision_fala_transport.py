"""Real probability floats must survive native Fala decision conduction."""

import json

import pytest
from test_implementation_selection_fala import run_graph
from test_issue_triage_fala import base_effector


@pytest.mark.parametrize('node', ['issue_triage', 'queue_conflict', 'intake_ambiguity'])
def test_native_decision_payload_survives_float_digest_boundary(tmp_path, node):
    event = {'event': 'typed_decision', 'node': 'issue_triage', 'repo': 'o/r', 'issue': 161,
             'status': 'completed', 'reason': 'decision_completed', 'choice': 'ready',
             'probabilities': {'ready': 0.9956357749455802, 'split': 0.0031688904248148133,
                              'host_ops_split': 0.00016794503980817048, 'host_ops': 7.933161950413796e-05,
                              'skip': 0.0008012209741597087, 'repo_shape': 7.452515965633552e-05,
                              'named_paths': 4.811705951391642e-05, 'linked_prs': 2.4194776962704266e-05},
             'confidence': 0.9956357749455802, 'label_mass': 0.9926058547596968,
             'usage': {'prompt_tokens': 4674, 'completion_tokens': 0, 'total_tokens': 4674}}
    # Captured GLM probabilities include exponent-form floats and full precision.
    trace = {**event, 'node': node}
    raw = {'ok': True, 'route': 'completed', 'stdout': json.dumps({
        'verdict': 'ready', 'reason': 'decision_ready', 'evidence': [],
        'evidence_kind': None, 'summary': 'Typed decision'}), 'decision_trace': trace}
    script = base_effector(f"""if a == 'get_issue':
    from lokay.typed_decisions import _record
    from types import SimpleNamespace
    import time
    cfg = SimpleNamespace(state_path=Path({str(tmp_path / 'state.jsonl')!r}))
    trace = _record(cfg, {trace!r}, time.monotonic())
    v.update({raw!r}, decision_trace=trace)
elif a == 'resolve_issue_candidate':
    from lokay.organ.common import _conduction_values
    result = _conduction_values(m)['get_issue']
    Path({str(tmp_path / 'conduction.json')!r}).write_text(json.dumps(result))
    v.update(route='skip')
""")
    graph = run_graph(tmp_path, script, 'probability-transport', path_id='issue_triage')
    assert graph['effector_results']['get_issue']['status'] == 'succeeded', graph['effector_results']['get_issue']
    transported = json.loads((tmp_path / 'conduction.json').read_text())
    assert transported['stdout'] == raw['stdout']
    assert transported['decision_trace']['choice'] == trace['choice']
    events = [json.loads(s) for s in (tmp_path / 'decisions.jsonl').read_text().splitlines()]
    assert events[0]['probabilities'] == event['probabilities']
