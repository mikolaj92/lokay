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
             existing=False, accepted=False, changed=False, invalid=False, unknown=False):
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
            return {'result': 'done'}
        for target, replacement in {
            'lokay.start.state_read': lambda *a: dict(saved),
            'lokay.start.state_update': update,
            'lokay.start.rounds_append': lambda *a: None,
            'lokay.start.run_dir': lambda *a: art.parent,
            'lokay.start.load_repos': lambda: [{'name': 'example/repo', 'clone_path': str(root / 'clone')}],
            'lokay.gh._gh': lambda *a: (0, json.dumps({'title': 'title', 'body': 'body'}), ''),
            'lokay.start.open_pr_for': lambda *a: None,
            'lokay.git.worktree_add': lambda *a: {'result': 'added'},
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
        if invalid:
            # Stop the existing structural retry after observing its persisted error.
            def stop_retry(*args):
                raise RuntimeError(saved['reason'])
            stack.enter_context(patch('lokay.start.time.sleep', stop_retry))
        picked = {'repo': 'example/repo', 'issue': 1, 'node': node}
        error = None
        try:
            start.advance.__wrapped__(picked)
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
        if builds and decisions:
            assert builds == [decisions[-1]], events
            assert events[-2][0] == 'decide', events
        if prompts and not invalid:
            assert [text for kind, text in events if kind == 'write'] == decisions[-len(prompts):], events
        if 'revise' in choices[:-1]:
            assert 'k_testy' in prompts[1], prompts
        if expected_error == 'limit':
            # A runtime retry must not reset the budget and eventually reach Build.
            before = list(events)
            try:
                start.advance.__wrapped__(picked)
            except RuntimeError as exc:
                assert 'limit' in str(exc), exc
            else:
                raise AssertionError('exhausted planning resumed')
            assert events == before, events
        print(f'{choices}: writes={len(prompts)}; decide={len(decisions)}; build={len(builds)}; error={error}')

run_case(['revise'] * 3, expected_error='limit')
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
