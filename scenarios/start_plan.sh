#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
uv run python - <<'PY'
import hashlib
import json
import tempfile
from collections import Counter
from contextlib import ExitStack, contextmanager
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from lokay import plan, start
from lokay.run import TickExpired, tick_deadline


def answers(choice):
    return {
        'next': {'choice': choice, 'confidence': 0.9},
        **{name: {'probabilities': {'true': 0.2 if choice == 'revise' else 0.9}}
           for name in plan.CRITERIA},
    }


@contextmanager
def scenario(*, choices=None, writes=None, node='plan', existing=False,
             accepted=False, changed=False, build_failure=None, pause=None,
             invalid_synthesis=False):
    with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
        root = Path(tmp)
        art = root / 'run' / 'plan.md'
        saved = {'node': node}
        if existing:
            art.parent.mkdir()
            art.write_text('\n'.join(plan.SECTIONS) + '\nprevious version')
        if accepted:
            saved['plan_accepted_sha'] = hashlib.sha256(art.read_bytes()).hexdigest()
        if changed:
            art.write_text(art.read_text() + '\nchanged after acceptance')
        choices = {name: list(values) for name, values in (choices or {}).items()}
        writes = {name: list(values) for name, values in (writes or {}).items()}
        events, prompts, syntheses, logs = [], [], [], []
        counts = Counter()
        paused = False
        clock = [9.0]

        def update(repo, issue, **values):
            # Match persisted state: mutations of a read must not silently save it.
            event = {"ts": clock[0], **values.pop("_event", {}), "fields": deepcopy(values)}
            saved.update(start.step(saved, event))

        def maybe_pause(kind, name):
            nonlocal paused
            if not paused and pause == (kind, name):
                paused = True
                raise TickExpired()

        def write(prompt, artifact):
            name = artifact.stem
            events.append(('write', name))
            prompts.append((name, prompt))
            maybe_pause('write', name)
            counts[name] += 1
            result = writes.get(name, []).pop(0) if writes.get(name) else 'done'
            if result == 'failed':
                return {'result': 'failed', 'reason': f'{name} writer failed'}
            artifact.write_text('missing sections' if result == 'invalid' else
                                '\n'.join(plan.SECTIONS) + f'\n{name} version {counts[name]}')
            return {'result': 'done'}

        def decide(request):
            text = request['state']['plan']
            name = 'synthesis' if text.startswith('## Cel\nsynthesis') else text.splitlines()[-1].split()[0]
            events.append(('decide', name))
            maybe_pause('decide', name)
            choice = choices.get(name, []).pop(0) if choices.get(name) else 'ok'
            if isinstance(choice, Exception):
                raise choice
            return answers(choice)

        def pi_step(prompt, artifact, **kwargs):
            assert artifact.name == 'synthesis.json', artifact
            inputs = {name: (art.parent / 'plans' / f'{name}.md').read_text()
                      for name in plan.PERSPECTIVES if f'Accepted branch: {name}\n' in prompt}
            assert inputs, prompt
            syntheses.append((inputs, prompt))
            events.append(('write', 'synthesis'))
            maybe_pause('write', 'synthesis')
            sources = list(inputs)
            row = {'tresc': 'Check observable behavior', 'zrodla': sources}
            data = {
                'cel': f'synthesis version {len(syntheses)}',
                'kryteria': [row], 'kroki': [row],
                'pliki': [{'sciezka': 'src/example.py', 'zmiana': 'Implement outcome', 'zrodla': sources}],
                'testy': [row], 'poza_zakresem': [row], 'odrzucone': [],
            }
            if invalid_synthesis:
                data['testy'][0]['zrodla'] = ['unaccepted']
            artifact.write_text(json.dumps(data))
            return {'result': 'done'}

        def build(worktree, text, *args, **kwargs):
            events.append(('build', text))
            assert text == art.read_text()
            assert saved['plan_accepted_sha'] == hashlib.sha256(text.encode()).hexdigest()
            return ({'result': 'failed', 'reason': build_failure, 'explanation': 'fixture explanation'}
                    if build_failure else {'result': 'done'})

        def sleep(*args):
            maybe_pause('sleep', saved.get('node'))

        def dependencies(*args):
            if pause == ('budget', 'build') and not paused:
                clock[0] = 10.0

        for target, replacement in {
            'lokay.start.state_read': lambda *a: deepcopy(saved),
            'lokay.start.state_update': update,
            'lokay.start.rounds_append': lambda repo, issue, text: logs.append(text),
            'lokay.start.run_dir': lambda *a: art.parent,
            'lokay.start.load_repos': lambda: [{'name': 'example/repo', 'clone_path': str(root / 'clone')}],
            'lokay.gh._gh': lambda *a: (0, json.dumps({'title': 'title', 'body': 'body'}), ''),
            'lokay.start.open_pr_for': lambda *a: None,
            'lokay.git.worktree_add': lambda *a: {'result': 'added'},
            'lokay.setup.prepare_dependencies': dependencies,
            'lokay.plan.plan_write': write,
            'lokay.plan.pi_step': pi_step,
            'lokay.decide.decide': decide,
            'lokay.build.build_code': build,
            'lokay.build.build_publish': lambda *a: {'result': 'pr_open', 'sha': 'head', 'pr': 1},
            'lokay.start._finish': lambda *a: {'result': 'pending'},
            'lokay.start.retry_sleep': sleep,
        }.items():
            stack.enter_context(patch(target, replacement))
        picked = {'repo': 'example/repo', 'issue': 1, 'node': node}

        def advance():
            return start.advance(picked)

        def complete():
            outcome = advance()
            assert outcome == {'result': 'pending'}, outcome
            assert saved['node'] == 'check' and saved['sha'] == 'head', saved
            assert saved['plan_synthesis']['phase'] == 'accepted' or accepted
            assert sum(kind == 'build' for kind, _ in events) == 1, events
            assert not any(choices.values()), choices
            assert not any(writes.values()), writes
            return outcome

        case = dict(advance=advance, complete=complete, saved=saved, events=events,
                    prompts=prompts, syntheses=syntheses, logs=logs, art=art, clock=clock)
        yield case


def branch_counts(case, kind):
    return Counter(name for event, name in case['events'] if event == kind and name in plan.PERSPECTIVES)


# Branch rejection has no retry cap, including identical fingerprints.
with scenario(choices={'minimal': ['revise'] * 7 + ['ok']}) as case:
    case['complete']()
    assert branch_counts(case, 'write') == {'minimal': 8, 'risk': 1, 'gates': 1}
    assert case['saved']['plan_rounds'] == 11
    assert case['saved']['plan_branches']['minimal']['rounds'] == 8
    for name, prompt in case['prompts'][1:8]:
        assert name == 'minimal' and 'Previous branch plan:' in prompt and 'k_testy' in prompt
print('branch revise: 7 rejections, 8 writes, no cap')

# Tick in branch 2 resumes branch 2, not accepted branch A. A completed write
# resumes at its decision; an interrupted write is run again.
for pause in [('write', 'risk'), ('decide', 'risk'), ('sleep', 'plan')]:
    choices = {'risk': ['revise', 'ok']} if pause[0] == 'sleep' else None
    with scenario(choices=choices, pause=pause) as case:
        outcome = case['advance']()
        assert outcome['reason'] == 'tick budget exhausted', outcome
        saved = case['saved']
        assert saved['node'] == 'plan' and not saved.get('plan_accepted_sha'), saved
        assert saved['plan_branches']['minimal']['phase'] == 'accepted'
        phase = 'check' if pause[0] == 'decide' else 'write'
        assert saved['plan_branches']['risk']['phase'] == phase, saved
        sha = saved['plan_branches']['minimal']['accepted_sha']
        before = len(case['events'])
        case['complete']()
        resumed = case['events'][before:]
        assert resumed[0] == ('decide' if pause[0] == 'decide' else 'write', 'risk'), resumed
        assert not any(name == 'minimal' for _, name in resumed), resumed
        assert case['saved']['plan_branches']['minimal']['accepted_sha'] == sha
        assert branch_counts(case, 'write') == {'minimal': 1, 'risk': 1 if pause[0] == 'decide' else 2, 'gates': 1}
print('TickExpired: branch 2 write/check/revise resume, branch A unchanged')

# A failed branch is terminal across ticks, just like an accepted branch.
with scenario(writes={'minimal': ['failed']}, pause=('write', 'risk')) as case:
    outcome = case['advance']()
    assert outcome['reason'] == 'tick budget exhausted', outcome
    saved = case['saved']
    assert saved['node'] == 'plan' and not saved.get('plan_accepted_sha'), saved
    failed = deepcopy(saved['plan_branches']['minimal'])
    assert failed['phase'] == 'failed', failed
    assert saved['plan_branches']['risk']['phase'] == 'write', saved
    assert not case['syntheses']
    before = len(case['events'])
    case['complete']()
    resumed = case['events'][before:]
    assert resumed[0] == ('write', 'risk'), resumed
    assert not any(name == 'minimal' for _, name in resumed), resumed
    assert saved['plan_branches']['minimal'] == failed
    assert branch_counts(case, 'write') == {'minimal': 1, 'risk': 2, 'gates': 1}
    assert branch_counts(case, 'decide') == {'risk': 1, 'gates': 1}
    assert len(case['syntheses']) == 1
    inputs, prompt = case['syntheses'][0]
    assert set(inputs) == {'risk', 'gates'}
    assert failed['reason'] in prompt and 'Failed branches:' in prompt
    data = json.loads((case['art'].parent / 'synthesis.json').read_text())
    assert plan.validate_synthesis(data, set(inputs)) == data
    assert case['art'].read_text() == plan.render_synthesis(data)
print('TickExpired after failed minimal: resume risk, no minimal retry, synthesize risk/gates')

# First synthesis rejection uses exactly the same accepted inputs. Repeated
# findings discard the graph and generate three fresh branches.
with scenario(choices={'synthesis': ['revise', 'revise', 'ok']}) as case:
    case['complete']()
    first, revised, fresh = case['syntheses']
    assert first[0] == revised[0] and first[0] != fresh[0]
    assert 'k_testy' in revised[1]
    assert 'Repeated synthesis rejection' in fresh[1]
    assert branch_counts(case, 'write') == dict.fromkeys(plan.PERSPECTIVES, 2)
    assert case['saved']['plan_rounds'] == 9
    assert len(case['saved']['plan_history']) == 1
    assert case['saved']['plan_synthesis']['rounds'] == 1
print('synthesis revise: same inputs once; repeated fingerprint: 3 fresh branches')

# Preserve accepted branches while retrying synthesis after a tick.
with scenario(pause=('write', 'synthesis')) as case:
    assert case['advance']()['reason'] == 'tick budget exhausted'
    case['complete']()
    assert case['syntheses'][0][0] == case['syntheses'][1][0]
    assert branch_counts(case, 'write') == dict.fromkeys(plan.PERSPECTIVES, 1)

# Partial failures are excluded from synthesis, not treated as accepted input.
for failure in ('failed', 'invalid', 'decision'):
    kwargs = ({'choices': {'risk': [RuntimeError('decision failed')]}} if failure == 'decision'
              else {'writes': {'risk': [failure]}})
    with scenario(**kwargs) as case:
        case['complete']()
        inputs, prompt = case['syntheses'][0]
        assert set(inputs) == {'minimal', 'gates'}
        assert case['saved']['plan_branches']['risk']['phase'] == 'failed'
        reason = case['saved']['plan_branches']['risk']['reason']
        assert reason in prompt and 'Failed branches:' in prompt
        data = json.loads((case['art'].parent / 'synthesis.json').read_text())
        assert plan.validate_synthesis(data, set(inputs)) == data
        assert case['art'].read_text() == plan.render_synthesis(data)
print('partial failures: writer, invalid plan, decision; only accepted sources reach synthesis')

# All branches fail once; replan then succeeds rather than synthesizing zero inputs.
with scenario(writes={name: ['failed', 'done'] for name in plan.PERSPECTIVES}) as case:
    case['complete']()
    assert branch_counts(case, 'write') == dict.fromkeys(plan.PERSPECTIVES, 2)
    assert len(case['syntheses']) == 1
    assert 'Wszystkie 3 plany nieudane' in case['syntheses'][0][1]
    assert len(case['saved']['plan_history']) == 1
    assert len(case['saved']['plan_history'][0]['uwagi']) == 3
print('all failures: replan, then 3 fresh branches and one synthesis')

with scenario(invalid_synthesis=True) as case:
    outcome = case['advance']()
    assert outcome['result'] == 'failed' and 'invalid synthesis' in outcome['reason'], outcome
    assert not case['art'].exists()
    assert not any(kind == 'build' for kind, _ in case['events'])

original_verdict = plan.verdict
with scenario() as case, patch('lokay.plan.verdict', side_effect=lambda wire:
        {'next': 'ship'} if case['syntheses'] else original_verdict(wire)):
    outcome = case['advance']()
    assert outcome['result'] == 'failed' and 'unknown plan verdict' in outcome['reason'], outcome
    assert not any(kind == 'build' for kind, _ in case['events'])
print('invalid synthesis and unknown verdict: no Build')

# Build feedback must clear both branch and synthesis acceptance before replan.
for reason in ('no_changes', 'outside_worktree', 'pi_exit'):
    with scenario(build_failure=reason) as case:
        outcome = case['advance']()
        assert outcome['result'] == 'failed' and outcome['next'] == 'plan', outcome
        saved = case['saved']
        assert saved['node'] == 'plan' and saved['plan_phase'] == 'write', saved
        assert saved['plan_branches'] == {} and saved['plan_synthesis'] == {}
        assert saved['plan_evaluations'] == 0 and saved['plan_accepted_sha'] is None
        assert saved['retry_at'] == 0 and saved['failures'] == 1
        prompt = saved['plan_prompt']
        assert prompt.startswith(plan.prompt_for('title', 'body'))
        assert f'Uwagi (Build): {reason}: fixture explanation' in prompt
        assert case['art'].read_text() in prompt and 'Rounds:' in prompt and 'Uwagi:' in prompt
        before = len(case['events'])
        # The next tick really starts fresh, not just empty state assertions.
        with patch('lokay.build.build_code', return_value={'result': 'done'}):
            assert case['advance']() == {'result': 'pending'}
        assert case['events'][before] == ('write', 'minimal')
        assert branch_counts(case, 'write') == dict.fromkeys(plan.PERSPECTIVES, 2)
print('Build → Plan: 3 failure reasons reset both graphs; next tick writes fresh branches')

# Existing Build plans must be accepted and unchanged to skip the graph.
for accepted, changed in ((False, False), (True, False), (True, True)):
    with scenario(node='build', existing=True, accepted=accepted, changed=changed) as case:
        outcome = case['advance']()
        assert outcome == {'result': 'pending'}, outcome
        skip = accepted and not changed
        assert branch_counts(case, 'write') == ({} if skip else dict.fromkeys(plan.PERSPECTIVES, 1))
        assert len(case['syntheses']) == (0 if skip else 1)
        assert sum(kind == 'build' for kind, _ in case['events']) == 1

# Real deadline exhaustion after acceptance preserves the Build node and SHA.
with scenario(pause=('budget', 'build')) as case, patch('lokay.run.time.monotonic', side_effect=lambda: case['clock'][0]):
    token = tick_deadline.set(10.0)
    try:
        assert case['advance']()['reason'] == 'tick budget exhausted'
        saved = case['saved']
        assert saved['node'] == 'build' and saved['plan_phase'] is None
        sha = saved['plan_accepted_sha']
        before = len(case['events'])
        case['clock'][0] = 9.0
        with patch('lokay.setup.prepare_dependencies'):
            case['complete']()
        assert case['saved']['plan_accepted_sha'] == sha
        assert [kind for kind, _ in case['events'][before:]] == ['build']
    finally:
        tick_deadline.reset(token)
print('Build resume: accepted unchanged plan skips graph; modified plan reruns graph')
print('start_plan: all scenarios passed')
PY
