"""One typed choice per configured semantic node; no retries or model fallback."""

from __future__ import annotations

import hashlib
import json
import math
import time
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from lokay.state import append_event


NODES = frozenset({'intake_ambiguity', 'issue_triage', 'queue_conflict', 'relocalization'})


def validate_configuration(endpoints: dict, routes: dict) -> None:
    if not isinstance(endpoints, dict) or not isinstance(routes, dict):
        raise ValueError('decisions endpoints and routes must be objects')
    for node, name in routes.items():
        if node not in NODES or name not in endpoints:
            raise ValueError(f'decisions unknown route or endpoint: {node!r}')
    for name, item in endpoints.items():
        if not isinstance(item, dict):
            raise ValueError(f'decisions endpoint {name!r} must be an object')
        protocol = item.get('protocol')
        url = urlsplit(str(item.get('url') or ''))
        if protocol not in {'systemone', 'decisions'} or url.scheme not in {'http', 'https'} or not url.hostname or url.username or url.password or url.query or url.fragment or url.path != f'/v1/{protocol}':
            raise ValueError(f'decisions endpoint {name!r} needs an explicit protocol and URL')
        if not isinstance(item.get('model'), str) or not item['model'].strip():
            raise ValueError(f'decisions endpoint {name!r} requires model identity')
        for key, low, high in [('timeout_seconds', 0, 180), ('min_confidence', .5, 1), ('max_input_chars', 0, 200000)]:
            value = item.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low < value <= high:
                raise ValueError(f'decisions endpoint {name!r} invalid {key}')


def _post(endpoint: dict, payload: dict) -> dict:
    # macOS local-network permission is executable-specific: uv Python cannot
    # reach GB10 on this host, while system curl can. One transport, no fallback.
    with tempfile.TemporaryDirectory(prefix='lokay-decision-') as directory:
        output = Path(directory) / 'response.json'
        result = subprocess.run([
            '/usr/bin/curl', '--disable', '--silent', '--show-error', '--noproxy', '*',
            '--proto', '=http,https', '--max-time', str(endpoint['timeout_seconds']),
            '--max-filesize', '1000000', '--header', 'Content-Type: application/json',
            '--data-binary', '@-', '--output', str(output), '--write-out', '%{http_code}',
            '--url', endpoint['url'],
        ], input=json.dumps(payload).encode(), capture_output=True,
            timeout=endpoint['timeout_seconds'] + 2)
        status = int(result.stdout) if result.stdout.isdigit() else 0
        if result.returncode or status != 200:
            return {'ok': False, 'http_status': status, 'transport_exit': result.returncode}
        return {'ok': True, 'data': json.loads(output.read_bytes())}


def configured(cfg, node: str) -> bool:
    return node in getattr(cfg, 'decision_routes', {})


def decide(cfg, *, node: str, evidence: dict, instructions: str,
           options: dict[str, str], identity: dict) -> dict:
    started = time.monotonic()
    state = json.dumps(evidence, ensure_ascii=False, sort_keys=True)
    name = cfg.decision_routes[node]
    endpoint = cfg.decision_endpoints.get(name, {})
    trace = {
        'event': 'typed_decision', 'node': node,
        **{key: identity.get(key) for key in ('repo', 'issue', 'pr', 'head_sha', 'base_sha')},
        'endpoint': name, 'model': endpoint.get('model'),
        'evidence_sha256': hashlib.sha256(state.encode()).hexdigest(),
        'status': 'failed', 'reason': 'decision_configuration_invalid',
    }
    try:
        validate_configuration(cfg.decision_endpoints, cfg.decision_routes)
        if len(state) > endpoint['max_input_chars']:
            trace['reason'] = 'decision_input_too_large'
            return _record(cfg, trace, started)
        protocol = endpoint['protocol']
        if protocol == 'systemone':
            payload = {'state': state, 'questions': {node: {
                'type': 'choice', 'instructions': instructions, 'criteria': options,
            }}}
        elif protocol == 'decisions':
            payload = {'model': endpoint['model'], 'input': state, 'questions': [{
                'id': node, 'type': 'choice', 'question': instructions,
                'options': [{'name': k, 'description': v} for k, v in options.items()],
            }], 'chat_template_kwargs': {'enable_thinking': False}, 'prompt_format_version': 1}
        else:
            raise ValueError('unsupported protocol')
        trace['request_sha256'] = hashlib.sha256(json.dumps(payload).encode()).hexdigest()
        trace['reason'] = 'decision_response_invalid'
        response = _post(endpoint, payload)
        if not response['ok']:
            trace.update(reason='decision_request_failed', http_status=response['http_status'], transport_exit=response['transport_exit'])
            return _record(cfg, trace, started)
        trace['reason'] = 'decision_response_invalid'
        trace['http_status'] = 200
        data = response['data']
        if set(data['answers']) != {node}:
            raise ValueError('question identity mismatch')
        if protocol == 'decisions' and (data.get('object') != 'decisions' or data.get('prompt_format_version') != 1):
            raise ValueError('protocol identity mismatch')
        answer = data['answers'][node]
        probabilities = answer['probabilities']
        if data['model'] != endpoint['model'] or answer['type'] != 'choice' or set(probabilities) != set(options):
            raise ValueError('decision identity or option coverage mismatch')
        if any(isinstance(p, bool) or not isinstance(p, (int, float)) or not math.isfinite(p) or not 0 <= p <= 1 for p in probabilities.values()) or abs(sum(probabilities.values()) - 1) > 1e-5:
            raise ValueError('invalid probabilities')
        choice = answer['choice']
        if choice not in options or probabilities[choice] != max(probabilities.values()):
            raise ValueError('choice is not an argmax')
        usage = data['usage']
        output_key = 'output_tokens' if protocol == 'systemone' else 'completion_tokens'
        if usage.get(output_key) != 0:
            raise ValueError('decision generated text')
        if protocol == 'decisions':
            mass = answer.get('label_mass')
            if isinstance(mass, bool) or not isinstance(mass, (int, float)) or not math.isfinite(mass) or not 0 <= mass <= 1.00001:
                raise ValueError('invalid label mass')
            trace['label_mass'] = mass
        confidence = probabilities[choice]
        accepted = confidence >= endpoint['min_confidence'] and list(probabilities.values()).count(confidence) == 1
        trace.update(status='completed' if accepted else 'abstained',
                     reason='decision_completed' if accepted else 'decision_uncertain',
                     choice=choice, probabilities=probabilities, confidence=confidence, usage=usage)
    except (KeyError, ValueError, TypeError, AttributeError) as exc:
        trace.update(status='failed', error_type=type(exc).__name__)
    except (OSError, subprocess.SubprocessError) as exc:
        trace.update(status='failed', reason='decision_request_failed', error_type=type(exc).__name__)
    return _record(cfg, trace, started)


def _record(cfg, trace: dict, started: float) -> dict:
    trace['duration_ms'] = round((time.monotonic() - started) * 1000, 2)
    try:
        append_event(cfg.state_path.with_name('decisions.jsonl'), trace, durable=True)
    except OSError:
        trace.update(status='failed', reason='decision_record_failed')
    return trace
