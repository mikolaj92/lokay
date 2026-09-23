"""Host-observed revisions around a coding invocation, never agent assertions."""
from pathlib import Path

from lokay.proc.pr_repair_push import _git_value


def observe(run, worktree: Path) -> dict:
    if not (worktree / '.git').exists():
        return {}
    values = {}
    for key, args in (
        ('head', ('rev-parse', '--verify', 'HEAD^{commit}')),
        ('branch', ('symbolic-ref', '--quiet', '--short', 'HEAD')),
        ('origin', ('remote', 'get-url', 'origin')),
    ):
        status, value, error = _git_value(run, worktree, *args)
        if status or error or not value:
            return {}
        values[key] = value
    return values


def _identity(observed: dict, inputs: dict) -> None:
    head = observed.get('head')
    if (not isinstance(head, str) or len(head) != 40
            or any(c not in '0123456789abcdef' for c in head)
            or observed.get('branch') != inputs['branch']
            or str(observed.get('origin') or '').removesuffix('.git') not in {
                'https://github.com/' + inputs['repo'],
                'git@github.com:' + inputs['repo'],
                'ssh://git@github.com/' + inputs['repo'],
            }):
        raise ValueError('repair revision repository/branch/target mismatch')


def commit_target(commit: dict, *, preceding: str, inputs: dict, worktree: str) -> str:
    """Bind a deterministic effect to its exact preceding host observation."""
    if commit.get('committed') is not True or commit.get('worktree') != worktree:
        raise ValueError('repair revision commit missing')
    if commit.get('committed_by') == 'agent':
        if commit.get('commit') and commit['commit'] != preceding:
            raise ValueError('repair agent commit target mismatch')
        return preceding
    revision = commit.get('revision') or {}
    before, after = revision.get('before') or {}, revision.get('after') or {}
    for observed in (before, after):
        _identity(observed, inputs)
    target = commit.get('commit')
    if (not isinstance(target, str) or before.get('head') != preceding or after.get('head') != target
            or target == preceding or revision.get('parents') != [preceding]):
        raise ValueError('repair deterministic commit continuity mismatch')
    return target


def verified_commit_target(*, commit: dict, inputs: dict, run_ref: dict, worktree: str) -> str:
    preceding = verified_target(
        inputs=inputs, run_ref=run_ref, worktree=worktree, allow_unchanged=True,
    )
    return commit_target(commit, preceding=preceding, inputs=inputs, worktree=worktree)


def verified_target(*, inputs: dict, run_ref: dict, worktree: str,
                    allow_unchanged: bool = False) -> str:
    """Require a continuous, exact, same-run harness history from admission.

    Historical runs lacking these observations cannot be upgraded from HEAD or
    ancestry. The caller journals the returned target; tests bind it separately.
    """
    from lokay.proc.pr_repair_checkpoint import _IDENTITY, _output, _rows, admitted_head

    rows = _rows(run_ref, 'pr_repair')
    admission = _output(rows, 'worktree_add')
    original = rows['worktree_add']['input']
    start = inputs['head_sha']
    if (any(original.get(k) != inputs.get(k) for k in _IDENTITY)
            or admission.get('route') != 'ready'
            or admission.get('worktree') != worktree):
        raise ValueError('agent revision admission mismatch')
    head = admitted_head(inputs, admission)
    found = False
    for name in ('run_agent', 'pr_repair_retry_agent', 'evidence_repair_agent',
                 'commit_initial_repair', 'pr_test_repair_agent'):
        if name not in rows:
            continue
        if name == 'commit_initial_repair':
            # The deterministic first commit may sit between the initial harness
            # and the test-repair harness. Do not use the commit being verified
            # as its own authority.
            if 'pr_test_repair_agent' in rows:
                initial = _output(rows, name)
                if any(rows[name]['input'].get(k) != original.get(k) for k in _IDENTITY):
                    raise ValueError('agent revision initial commit mismatch')
                head = commit_target(initial, preceding=head, inputs=inputs, worktree=worktree)
            continue
        if any(rows[name]['input'].get(k) != original.get(k) for k in _IDENTITY):
            raise ValueError('agent revision run lineage mismatch')
        output = _output(rows, name)
        agent = output if name == 'run_agent' else output.get('agent') or {}
        revision = agent.get('revision') or {}
        before, after = revision.get('before') or {}, revision.get('after') or {}
        if (agent.get('status') != 'completed' or agent.get('returncode') != 0
                or agent.get('timed_out') or agent.get('worktree') != worktree
                or before.get('head') != head):
            raise ValueError('agent revision execution evidence missing')
        for observed in (before, after):
            _identity(observed, inputs)
        head = after['head']
        found = True
    if not found or (head == start and not allow_unchanged):
        raise ValueError('agent revision exact target missing')
    return head
