"""Each owning semantic adapter speaks Decisions, once, with no prose fallback."""

import json
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from lokay.config import load_config
from lokay.typed_decisions import NODES


@pytest.mark.parametrize('node', sorted(NODES))
def test_gb10_request_at_real_semantic_owner(tmp_path, monkeypatch, node):
    calls = []
    choices = {'intake_ambiguity': 'pass', 'issue_triage': 'ready',
               'queue_conflict': 'ready', 'relocalization': 'required'}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            calls.append((self.path, payload))
            question, = payload['questions']
            names = [option['name'] for option in question['options']]
            answer = {'type': 'choice', 'choice': choices[node], 'label_mass': .99,
                      'probabilities': {name: .98 if name == choices[node] else .02 / (len(names) - 1)
                                        for name in names}}
            data = json.dumps({'object': 'decisions', 'prompt_format_version': 1,
                               'model': 'GLM-5.3-Flash-EXL3', 'answers': {node: answer},
                               'usage': {'prompt_tokens': 10, 'completion_tokens': 0}}).encode()
            self.send_response(200)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    cfg = load_config('config.live-autonomous.example.yaml')
    cfg.state_path = tmp_path / 'state.jsonl'
    cfg.decision_endpoints['gb10']['url'] = f'http://127.0.0.1:{server.server_port}/v1/decisions'
    cfg.config_path = tmp_path / 'config.yaml'
    import yaml
    cfg.config_path.write_text(yaml.safe_dump({'mode': 'live',
        'state': {'path': str(cfg.state_path)},
        'decisions': {'endpoints': cfg.decision_endpoints, 'routes': cfg.decision_routes}}))

    def forbidden(*a, **kw):
        pytest.fail('unexpected generative fallback')

    monkeypatch.setattr('lokay.proc._prose_agent._run', forbidden)
    monkeypatch.setattr('lokay.proc._issue_triage_agent_runtime.run_agent', forbidden)
    monkeypatch.setattr('lokay.proc.run_queue_conflict_agent.run_agent', forbidden)
    monkeypatch.setattr('lokay.proc.run_relocalization_agent.run_agent', forbidden)
    issue = {'repo': 'o/r', 'number': 42, 'title': 'Rename OLD to NEW',
             'body': 'Rename constant OLD to NEW and migrate callers.', 'state': 'OPEN'}
    try:
        if node == 'intake_ambiguity':
            from lokay.proc.run_intake_ambiguity_check import run
            result = run({'config_path': str(cfg.config_path), 'live': True, 'issue': issue})
            assert result['check']['verdict'] == 'pass'
        elif node == 'issue_triage':
            from lokay.proc.run_issue_triage_agent import run
            result = run(cfg=cfg, repo='o/r', issue=42, issue_data=issue,
                         hard_facts={'route': 'agent'}, clone_path=tmp_path, live=True)
            assert json.loads(result['stdout'])['verdict'] == 'ready'
        elif node == 'queue_conflict':
            from lokay.proc.run_queue_conflict_agent import run
            result = run(cfg=cfg, target={'repo': 'o/r', 'issue': 42,
                         'candidate': issue, 'peer_issues': [], 'open_prs': []}, live=True)
            assert json.loads(result['stdout'])['outcome'] == 'ready'
        else:
            from lokay.proc.run_relocalization_agent import run
            root = tmp_path / 'repo'; root.mkdir()
            def git(*args):
                return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()
            git('init', '-q'); git('config', 'user.email', 'test@example.com'); git('config', 'user.name', 'Test')
            (root / 'caller.py').write_text('value = OLD\n')
            git('add', '.'); git('commit', '-qm', 'base')
            git('update-ref', 'refs/remotes/origin/main', git('rev-parse', 'HEAD'))
            (root / 'caller.py').write_text('value = NEW\n')
            result = run({'worktree': str(root), 'localized': ['product.py'], 'issue_raw': issue},
                         {'off_goal_paths': ['caller.py']}, config=cfg)
            assert result['route'] == 'validate'
            assert (root / 'caller.py').read_text() == 'value = NEW\n'
        assert len(calls) == 1
        path, request = calls[0]
        assert path == '/v1/decisions'
        assert request['model'] == 'GLM-5.3-Flash-EXL3'
        assert [q['id'] for q in request['questions']] == [node]
        events = [json.loads(line) for line in (tmp_path / 'decisions.jsonl').read_text().splitlines()]
        assert len(events) == 1
        assert events[0]['endpoint'] == 'gb10'
        assert events[0]['model'] == 'GLM-5.3-Flash-EXL3'
        assert events[0]['status'] == 'completed'
    finally:
        server.shutdown(); server.server_close(); thread.join()
