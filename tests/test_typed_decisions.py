import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from lokay.config import Config, load_config


@pytest.fixture
def endpoint():
    calls = []
    response = {'model': 'plumb-test', 'answers': {'intake_ambiguity': {
        'type': 'choice', 'choice': 'pass', 'probabilities': {'pass': .96, 'split': .03, 'park': .01},
    }}, 'usage': {'input_tokens': 12, 'output_tokens': 0}}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            calls.append((self.path, json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
            data = json.dumps(response).encode()
            self.send_response(response.get('_http_status', 200))
            if '_location' in response:
                self.send_header('Location', response['_location'])
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f'http://127.0.0.1:{server.server_port}', calls, response
    server.shutdown()
    server.server_close()
    thread.join()


def config(tmp_path, url, protocol='systemone'):
    path = tmp_path / 'config.yaml'
    path.write_text(f'''mode: live
state:
  path: {tmp_path / 'state.jsonl'}
decisions:
  endpoints:
    local:
      url: {url}/v1/{'systemone' if protocol == 'systemone' else 'decisions'}
      protocol: {protocol}
      model: plumb-test
      min_confidence: 0.85
      timeout_seconds: 2
      max_input_chars: 24000
  routes:
    intake_ambiguity: local
''')
    return load_config(path)


def test_systemone_one_call_records_identity_probabilities_and_evidence(tmp_path, endpoint):
    from lokay.typed_decisions import decide

    url, calls, _ = endpoint
    cfg = config(tmp_path, url)
    result = decide(cfg, node='intake_ambiguity', evidence={'body': 'One change'},
                    instructions='Classify scope', options={'pass': 'one change', 'split': 'several changes', 'park': 'insufficient evidence'},
                    identity={'repo': 'owner/repo', 'issue': 42, 'head_sha': 'abc'})
    assert result['status'] == 'completed'
    assert result['choice'] == 'pass'
    assert len(calls) == 1
    assert calls[0][0] == '/v1/systemone'
    assert list(calls[0][1]['questions']) == ['intake_ambiguity']
    events = [json.loads(x) for x in (tmp_path / 'decisions.jsonl').read_text().splitlines()]
    assert len(events) == 1
    assert events[0]['repo'] == 'owner/repo'
    assert events[0]['issue'] == 42
    assert events[0]['head_sha'] == 'abc'
    assert len(events[0]['evidence_sha256']) == 64
    assert events[0]['probabilities']['pass'] == .96
    assert events[0]['model'] == 'plumb-test'
    assert len(events[0]['request_sha256']) == 64
    import hashlib
    # The journal identifies exact transmitted bytes, including option order.
    assert events[0]['request_sha256'] == hashlib.sha256(json.dumps(calls[0][1]).encode()).hexdigest()


@pytest.mark.parametrize('change,reason', [
    ({'choice': 'split', 'probabilities': {'pass': .34, 'split': .35, 'park': .31}}, 'decision_uncertain'),
    ({'choice': 'invented'}, 'decision_response_invalid'),
    ({'probabilities': {'pass': float('nan'), 'split': .03, 'park': .01}}, 'decision_response_invalid'),
    ({'probabilities': {'pass': .96, 'split': .03}}, 'decision_response_invalid'),
    ({'choice': 'park'}, 'decision_response_invalid'),
])
def test_invalid_or_uncertain_is_terminal_without_second_call(tmp_path, endpoint, change, reason):
    from lokay.typed_decisions import decide
    url, calls, response = endpoint
    response['answers']['intake_ambiguity'].update(change)
    result = decide(config(tmp_path, url), node='intake_ambiguity', evidence={}, instructions='scope',
                    options={'pass': 'one', 'split': 'several', 'park': 'unclear'}, identity={})
    assert result['status'] != 'completed'
    assert result['reason'] == reason
    assert len(calls) == 1


def test_decisions_protocol_and_model_identity(tmp_path, endpoint):
    from lokay.typed_decisions import decide
    url, calls, response = endpoint
    cfg = config(tmp_path, url, 'decisions')
    response['answers']['intake_ambiguity']['label_mass'] = .9
    response['object'] = 'decisions'
    response['prompt_format_version'] = 1
    response['usage'] = {'prompt_tokens': 12, 'completion_tokens': 0}
    result = decide(cfg, node='intake_ambiguity', evidence={'body': 'One'}, instructions='scope',
                    options={'pass': 'one', 'split': 'several', 'park': 'unclear'}, identity={})
    assert result['status'] == 'completed'
    assert len(calls) == 1
    assert calls[0][0] == '/v1/decisions'
    assert calls[0][1]['questions'][0]['options'][1]['name'] == 'split'
    response['model'] = 'foreign-model'
    result = decide(cfg, node='intake_ambiguity', evidence={}, instructions='scope',
                    options={'pass': 'one', 'split': 'several', 'park': 'unclear'}, identity={})
    assert result['reason'] == 'decision_response_invalid'


@pytest.mark.parametrize('change', [{'prompt_format_version': 2}, {'object': 'chat.completion'}])
def test_decisions_rejects_protocol_identity_drift(tmp_path, endpoint, change):
    from lokay.typed_decisions import decide
    url, calls, response = endpoint
    response.update(object='decisions', prompt_format_version=1, usage={'completion_tokens': 0})
    response['answers']['intake_ambiguity']['label_mass'] = .9
    response.update(change)
    out = decide(config(tmp_path, url, 'decisions'), node='intake_ambiguity', evidence={}, instructions='scope',
                 options={'pass': 'one', 'split': 'several', 'park': 'unknown'}, identity={})
    assert out['reason'] == 'decision_response_invalid'
    assert out['status'] == 'failed'
    assert len(calls) == 1


def test_oversized_evidence_is_not_silently_truncated_or_sent(tmp_path, endpoint):
    from lokay.typed_decisions import decide
    url, calls, _ = endpoint
    result = decide(config(tmp_path, url), node='intake_ambiguity', evidence={'body': 'a' * 24001},
                    instructions='scope', options={'pass': 'one', 'park': 'unclear'}, identity={})
    assert result['reason'] == 'decision_input_too_large'
    assert calls == []


def test_invalid_decision_configuration_rejected_at_load(tmp_path):
    path = tmp_path / 'bad.yaml'
    path.write_text('decisions:\n  endpoints: {}\n  routes:\n    test_local: unknown\n')
    with pytest.raises(ValueError, match='decisions'):
        load_config(path)


def test_intake_uses_plumb_not_prose_agent_and_abstains_fail_closed(tmp_path, endpoint, monkeypatch):
    from lokay.proc.run_intake_ambiguity_check import run
    url, calls, response = endpoint
    cfg = config(tmp_path, url)
    monkeypatch.setattr('lokay.proc._prose_agent._run', lambda *a: pytest.fail('unexpected generative agent'))
    raw = {'config_path': str(cfg.config_path), 'live': True,
           'issue': {'repo': 'owner/repo', 'number': 42, 'title': 'Fix one function', 'body': 'Make it return the documented value', 'state': 'OPEN'}}
    out = run(raw)
    assert out['check']['verdict'] == 'pass'
    assert len(calls) == 1
    response['answers']['intake_ambiguity']['probabilities'] = {'pass': .4, 'split': .35, 'park': .25}
    out = run(raw)
    assert out['check']['verdict'] == 'park'
    assert out['check']['reason'] == 'decision_uncertain'
    assert len(calls) == 2
    raw['live'] = False
    out = run(raw)
    assert out['check']['verdict'] == 'park'
    assert len(calls) == 2


def test_live_triage_graph_has_one_local_scope_node_before_glm_intent():
    import tomllib
    from pathlib import Path
    pkg = tomllib.loads(Path('src/lokay/data/lokay.fala-package.toml').read_text())
    graph = next(p for p in pkg['correlation_paths'] if p['id'] == 'issue_triage')
    nodes = {n['id']: n for n in graph['effectors']}
    assert 'issue_scope_decision' in nodes
    assert nodes['issue_scope_decision']['when']['upstream'] == 'resolve_issue_hard_facts'
    assert 'issue_scope_decision' in nodes['issue_triage_agent']['conduction']
    assert 'issue_scope_decision' in nodes['issue_evidence_agent']['conduction']


def test_triage_does_not_duplicate_issue_evidence_into_policy(tmp_path, endpoint):
    from lokay.proc.run_issue_triage_agent import run
    url, calls, _ = endpoint
    cfg = config(tmp_path, url)
    cfg.decision_routes = {'issue_triage': 'local'}
    run(cfg=cfg, repo='owner/repo', issue=42,
        issue_data={'repo': 'owner/repo', 'number': 42, 'title': 'EVIDENCE_SENTINEL', 'body': 'EVIDENCE_SENTINEL'},
        hard_facts={'route': 'agent'}, clone_path=None, live=True)
    payload = calls[0][1]
    assert 'EVIDENCE_SENTINEL' not in payload['questions']['issue_triage']['instructions']
    assert 'EVIDENCE_SENTINEL' in payload['state']


def test_issue_triage_uses_decision_verdict_and_handles_evidence_without_agent(tmp_path, endpoint, monkeypatch):
    from lokay.proc.run_issue_triage_agent import run
    from lokay.proc.run_issue_evidence_agent import run as evidence_run
    from lokay.issue_triage_boundary import validate_output
    url, calls, response = endpoint
    cfg = config(tmp_path, url)
    cfg.decision_routes = {'issue_triage': 'local'}
    response['answers'] = {'issue_triage': {'type': 'choice', 'choice': 'split',
        'probabilities': {'ready': .01, 'split': .95, 'host_ops_split': .01, 'host_ops': .01,
                          'skip': .005, 'repo_shape': .005, 'named_paths': .005, 'linked_prs': .005}}}
    monkeypatch.setattr('lokay.proc._issue_triage_agent_runtime.run_agent', lambda *a, **kw: pytest.fail('unexpected agent'))
    kwargs = dict(cfg=cfg, repo='owner/repo', issue=42, issue_data={'repo': 'owner/repo', 'number': 42, 'body': 'Implement two independent products'},
                  hard_facts={'route': 'agent'}, clone_path=tmp_path, live=True)
    out = run(**kwargs)
    parsed = validate_output(out['stdout'])
    assert parsed['decision']['verdict'] == 'split'
    assert len(calls) == 1
    # Additional physical evidence is a distinct node invocation, not a hidden retry.
    response['answers']['issue_triage']['choice'] = 'named_paths'
    response['answers']['issue_triage']['probabilities']['split'] = .005
    response['answers']['issue_triage']['probabilities']['named_paths'] = .95
    out = evidence_run(**kwargs, additional={'kind': 'named_paths', 'value': ['a.py']})
    assert validate_output(out['stdout'])['decision']['verdict'] == 'skip'
    assert len(calls) == 2


def test_queue_evidence_excludes_candidate_from_its_own_peers(tmp_path, endpoint):
    from lokay.proc.run_queue_conflict_agent import run
    url, calls, response = endpoint
    cfg = config(tmp_path, url); cfg.decision_routes = {'queue_conflict': 'local'}
    target = {'repo': 'owner/repo', 'issue': 42, 'candidate': {'number': 42},
              'peer_issues': [{'number': 42, 'title': 'Self'}, {'number': 43, 'title': 'Peer'}]}
    run(cfg=cfg, target=target, live=True)
    evidence = json.loads(calls[0][1]['state'])
    assert evidence['peer_issues'] == [{'number': 43, 'title': 'Peer'}]


def test_queue_decision_abstention_is_valid_skip_not_retry(tmp_path, endpoint, monkeypatch):
    from lokay.proc.run_queue_conflict_agent import run
    from lokay.proc.queue_conflict_boundary import validate
    url, calls, response = endpoint
    cfg = config(tmp_path, url)
    cfg.decision_routes = {'queue_conflict': 'local'}
    response['answers'] = {'queue_conflict': {'type': 'choice', 'choice': 'ready',
        'probabilities': {'ready': .4, 'skip': .3, 'superseded': .15, 'tracker': .15}}}
    monkeypatch.setattr('lokay.proc.run_queue_conflict_agent.run_agent', lambda *a, **kw: pytest.fail('unexpected agent'))
    out = run(cfg=cfg, target={'repo': 'owner/repo', 'issue': 42, 'candidate': {'body': 'Do one thing'}, 'open_prs': [], 'peer_issues': []}, live=True)
    parsed = validate(out['stdout'])
    assert parsed['route'] == 'valid'
    assert parsed['decision']['outcome'] == 'skip'
    assert parsed['decision']['reason'] == 'decision_uncertain'
    assert len(calls) == 1


@pytest.mark.parametrize('status', [503, 307])
def test_http_failure_and_redirect_do_not_retry_or_fallback(tmp_path, endpoint, status):
    from lokay.typed_decisions import decide
    url, calls, response = endpoint
    cfg = config(tmp_path, url)
    response['_http_status'] = status
    response['_location'] = url + '/redirect'
    out = decide(cfg, node='intake_ambiguity', evidence={}, instructions='scope', options={'pass': 'one', 'split': 'several', 'park': 'unknown'}, identity={})
    assert out['status'] == 'failed'
    assert out['reason'] == 'decision_request_failed'
    assert out['http_status'] == status
    assert len(calls) == 1


def test_relocalization_missing_worktree_is_named_terminal(tmp_path):
    from lokay.proc.semantic_relocalization import run
    cfg = Config(mode='live')
    out = run({}, {'off_goal_paths': ['a.py']}, config=cfg)
    assert out['reason'] == 'decision_scope_invalid'


def test_system_curl_is_the_single_request_transport(tmp_path, endpoint, monkeypatch):
    from lokay.typed_decisions import decide
    import subprocess
    url, calls, response = endpoint
    cfg = config(tmp_path, url)
    commands = []
    original = subprocess.run
    def run(argv, **kwargs):
        commands.append(argv)
        return original(argv, **kwargs)
    monkeypatch.setattr(subprocess, 'run', run)
    out = decide(cfg, node='intake_ambiguity', evidence={}, instructions='scope', options={'pass': 'one', 'split': 'several', 'park': 'unknown'}, identity={})
    assert out['status'] == 'completed'
    assert len(commands) == 1 and commands[0][0] == '/usr/bin/curl'
    assert len(calls) == 1


def test_relocalization_reads_actual_diff_in_one_request_and_keeps_source(tmp_path, endpoint, monkeypatch):
    import subprocess
    from lokay.proc.run_relocalization_agent import run
    from lokay.proc.build_relocalization_agent_request import build
    from lokay.proc.validate_localization_agent_json import validate
    url, calls, response = endpoint
    cfg = config(tmp_path, url)
    cfg.decision_routes = {'relocalization': 'local'}
    response['answers'] = {'relocalization': {'type': 'choice', 'choice': 'required',
        'probabilities': {'required': .98, 'unrelated': .01, 'uncertain': .01}}}
    root = tmp_path / 'repo'
    root.mkdir()
    def git(*args):
        return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()
    git('init', '-q'); git('config', 'user.email', 'test@example.com'); git('config', 'user.name', 'Test')
    (root / 'a.py').write_text('OLD = 1\n')
    git('add', '.'); git('commit', '-qm', 'base')
    head = git('rev-parse', 'HEAD')
    git('update-ref', 'refs/remotes/origin/main', head)
    (root / 'a.py').write_text('NEW = 1\n')
    evidence = {'worktree': str(root), 'localized': ['b.py'], 'issue_raw': {'repo': 'owner/repo', 'number': 42, 'title': 'Rename constant', 'body': 'Rename OLD to NEW.'}}
    request = build(evidence, {'route': 'agent', 'off_goal_paths': ['a.py']})
    monkeypatch.setattr('lokay.proc.run_relocalization_agent.run_agent', lambda *a, **kw: pytest.fail('unexpected agent'))
    out = run(evidence, request, config=cfg)
    assert validate(out)['paths'] == ['a.py']
    assert len(calls) == 1
    state = json.loads(calls[0][1]['state'])
    assert '-OLD = 1' in state['diff']
    assert '+NEW = 1' in state['diff']
    assert state['head_sha'] == head
    assert git('rev-parse', 'HEAD') == head
    assert (root / 'a.py').read_text() == 'NEW = 1\n'
    out = run(evidence, request, config=cfg, feedback='retry')
    assert out['route'] == 'terminal'
    assert out['reason'] == 'decision_retry_not_allowed'
    assert len(calls) == 1


def test_relocalization_untracked_file_change_during_request_is_rejected(tmp_path, monkeypatch):
    import subprocess
    from lokay.proc.semantic_relocalization import run
    root = tmp_path / 'repo'; root.mkdir()
    def git(*args):
        return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()
    git('init', '-q'); git('config', 'user.email', 'test@example.com'); git('config', 'user.name', 'Test')
    (root / 'a.py').write_text('old\n'); git('add', '.'); git('commit', '-qm', 'base')
    git('update-ref', 'refs/remotes/origin/main', git('rev-parse', 'HEAD'))
    extra = root / 'new.py'; extra.write_text('required\n')
    cfg = Config(mode='live', decision_routes={'relocalization': 'local'}, decision_endpoints={'local': {'max_input_chars': 24000}})
    def decide(*a, **kw):
        assert 'required' in kw['evidence']['diff']
        extra.write_text('unrelated\n')
        return {'status': 'completed', 'choice': 'required', 'reason': 'decision_completed'}
    monkeypatch.setattr('lokay.proc.semantic_relocalization.decide', decide)
    out = run({'worktree': str(root), 'issue_raw': {}}, {'off_goal_paths': ['new.py']}, config=cfg)
    assert out['route'] == 'terminal'
    assert out['reason'] == 'decision_scope_drift'
