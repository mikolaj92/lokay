#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
uv run python - <<'PY'
import json
import tempfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from lokay import plan, start


def answers(choice):
    return {
        'next': {'choice': choice, 'confidence': 0.9},
        **{name: {'probabilities': {'true': 0.2 if choice == 'revise' else 0.9}}
           for name in plan.CRITERIA},
    }


def run_case(choices, *, expected_build=0, expected_error=None, node='plan',
             existing=False, accepted=False, changed=False, invalid=False, unknown=False, build_failure=None,
             budget=False):
    with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
        root = Path(tmp)
        art = root / 'run' / 'plan.md'
        saved = {'node': node}
        if existing:
            art.parent.mkdir()
            art.write_text('\n'.join(plan.SECTIONS) + '\nprevious version')
        if accepted:
            import hashlib
            saved['plan_accepted_sha'] = hashlib.sha256(art.read_bytes()).hexdigest()
        if changed:
            art.write_text(art.read_text() + '\nchanged after acceptance')
        events = []
        prompts = []
        def update(repo, issue, **values):
            saved.update(values)
        def write(prompt, artifact):
            prompts.append(prompt)
            artifact.write_text('missing sections' if invalid else
                                '\n'.join(plan.SECTIONS) + f'\nversion {len(prompts)}')
            events.append(('write', artifact.read_text()))
            if budget == 'write' and len(prompts) == 1:
                from lokay.run import TickExpired
                raise TickExpired()
            return {'result': 'done'}
        iterator = iter(choices)
        def decide(request):
            events.append(('decide', request['state']['plan']))
            choice = next(iterator)
            if isinstance(choice, Exception):
                raise choice
            return answers(choice)
        def build(worktree, text, *args, **kwargs):
            events.append(('build', text))
            return ({'result': 'failed', 'reason': build_failure, 'explanation': 'fixture explanation'}
                    if build_failure else {'result': 'done'})
        for target, replacement in {
            'lokay.start.state_read': lambda *a: dict(saved),
            'lokay.start.state_update': update,
            'lokay.start.rounds_append': lambda *a: None,
            'lokay.start.run_dir': lambda *a: art.parent,
            'lokay.start.load_repos': lambda: [{'name': 'example/repo', 'clone_path': str(root / 'clone')}],
            'lokay.gh._gh': lambda *a: (0, json.dumps({'title': 'title', 'body': 'body'}), ''),
            'lokay.start.open_pr_for': lambda *a: None,
            'lokay.git.worktree_add': lambda *a: {'result': 'added'},
            'lokay.setup.prepare_dependencies': lambda *a: None,
            'lokay.plan.plan_write': write,
            'lokay.decide.decide': decide,
            'lokay.build.build_code': build,
            'lokay.build.build_publish': lambda *a: {'result': 'pr_open', 'sha': 'head', 'pr': 1},
            'lokay.start._finish': lambda *a: {'result': 'pending'},
            'lokay.start.time.sleep': lambda *a: None,
        }.items():
            stack.enter_context(patch(target, replacement))
        if unknown:
            stack.enter_context(patch('lokay.plan.verdict', return_value={'next': 'ship'}))
        picked = {'repo': 'example/repo', 'issue': 1, 'node': node}
        if budget:
            from lokay.run import tick_deadline
            clock = [9.0]
            stack.enter_context(patch('lokay.run.time.monotonic', side_effect=lambda: clock[0]))
            if budget == 'revise':
                stack.enter_context(patch('lokay.run.time.sleep',
                                          side_effect=lambda *a: clock.__setitem__(0, 10.0)))
            elif budget is True:
                stack.enter_context(patch('lokay.setup.prepare_dependencies',
                                          side_effect=lambda *a: clock.__setitem__(0, 10.0)))
            token = tick_deadline.set(10.0)
            try:
                outcome = start.advance(picked)
                assert outcome['result'] == 'pending', outcome
                assert not any(kind == 'build' for kind, _ in events), events
                if budget in ('write', 'revise'):
                    assert saved['node'] == 'plan' and saved['plan_phase'] == 'write', saved
                    assert saved['plan_prompt'] and not saved.get('plan_accepted_sha'), saved
                    assert saved.get('plan_rounds', 0) == int(budget == 'revise'), saved
                    if budget == 'revise':
                        assert 'Uwagi:' in saved['plan_prompt'] and 'k_testy' in saved['plan_prompt']
                    clock[0] = 9.0
                    assert start.advance(picked)['result'] == 'pending'
                    assert saved['node'] == 'check' and saved['plan_accepted_sha'], saved
                    assert len(prompts) == 2, prompts
                    assert [text for kind, text in events if kind == 'build'] == [art.read_text()]
                    assert saved['plan_rounds'] == (1 if budget == 'write' else 2), saved
                    return
                assert saved['node'] == 'build' and saved['plan_phase'] is None, saved
                accepted_sha = saved['plan_accepted_sha']
                assert accepted_sha and saved['issue_title'] == 'title'
                clock[0] = 9.0
                with patch('lokay.setup.prepare_dependencies'):
                    assert start.advance(picked)['result'] == 'pending'
                assert saved['sha'] == 'head' and saved['node'] == 'check', saved
                assert saved['plan_accepted_sha'] == accepted_sha
                assert [kind for kind, _ in events] == ['write', 'decide', 'build'], events
            finally:
                tick_deadline.reset(token)
            return
        error = None
        try:
            outcome = start.advance.__wrapped__(picked)
        except RuntimeError as exc:
            error = str(exc)
        builds = [text for kind, text in events if kind == 'build']
        decisions = [text for kind, text in events if kind == 'decide']
        assert len(builds) == expected_build, events
        assert len(decisions) == len(choices), events
        if expected_error:
            assert error and expected_error in error, error
        else:
            assert error is None, error
        if build_failure:
            assert outcome['result'] == 'failed' and outcome['next'] == 'plan', outcome
            assert saved['node'] == 'plan' and saved['plan_phase'] == 'write', saved
            assert saved['plan_evaluations'] == 0 and saved['plan_accepted_sha'] is None
            assert saved['plan_prompt'].startswith(plan.prompt_for('title', 'body'))
            assert f'Uwagi (Build): {build_failure}: fixture explanation' in saved['plan_prompt']
            assert decisions[-1] in saved['plan_prompt']
            assert 'Rounds:' in saved['plan_prompt'] and 'Uwagi:' in saved['plan_prompt']
            assert saved['retry_at'] == 0 and saved['failures'] == 1
        if builds and decisions:
            assert builds == [decisions[-1]], events
            assert events[-2][0] == 'decide', events
        if prompts and not invalid:
            assert [text for kind, text in events if kind == 'write'] == decisions[-len(prompts):], events
        if 'revise' in choices[:-1]:
            assert 'k_testy' in prompts[1] and decisions[0] in prompts[1], prompts
            assert len(saved['plan_history']) >= choices.count('revise')
            if choices.count('revise') > 1:
                assert 'Repeated plan rejection' in prompts[2], prompts
        print(f'{choices}: writes={len(prompts)}; decide={len(decisions)}; build={len(builds)}; error={error}')

run_case(['ok'], budget='write')
run_case(['revise', 'ok'], budget='revise')
run_case(['ok'], budget=True)
for reason in ('no_changes', 'outside_worktree', 'pi_exit'):
    run_case(['ok'], expected_build=1, build_failure=reason)
run_case(['revise'] * 4 + ['ok'], expected_build=1)
run_case(['ok'], expected_build=1)
run_case(['revise', 'ok'], expected_build=1)
run_case(['revise', 'revise', 'ok'], expected_build=1)
run_case([], invalid=True, expected_error='invalid plan')
run_case([RuntimeError('decision failed')], expected_error='decision failed')
run_case(['ok'], unknown=True, expected_error='unknown plan verdict')
run_case(['ok'], node='build', existing=True, expected_build=1)
run_case([], node='build', existing=True, accepted=True, expected_build=1)
run_case(['ok'], node='build', existing=True, accepted=True, changed=True, expected_build=1)
PY
