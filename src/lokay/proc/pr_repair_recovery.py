"""One exact-target retry effect. Fala owns selection and later confirmation."""
from __future__ import annotations

from pathlib import Path

from lokay.proc import pr_repair_receipts as receipts
from lokay.proc.pr_repair_checkpoint import verify_local
from lokay.proc.pr_repair_push import reconcile_pending_push


def _mutation_gate(config_path):
    from lokay.config import load_config
    from lokay.proc._common import mutations_allowed
    mutations_allowed(live_flag=True, cfg=load_config(config_path))


def _push_exact(*, proof: dict) -> dict:
    from lokay.proc._common import runner
    from lokay.runner import git_spec
    intent = proof['intent']
    result = runner().run(git_spec([
        'push', 'origin', intent['target_head_sha'] + ':refs/heads/' + intent['branch'],
    ], cwd=Path(proof['worktree']), timeout_seconds=300), live=True)
    return {'ok': result.returncode == 0, 'reason': 'repair_push_retry_failed' if result.returncode else ''}


def close_pending(*, observed: dict, config_path: str | None) -> dict:
    """Terminalize only after a fresh closed/merged exact repo/branch observation."""
    repo, pr = str(observed['repo']), int(observed['pr'])
    state = receipts.resolve_state_dir(config_path)
    if state is None:
        return {'ok': True, 'route': 'fail_closed', 'reason': 'repair_push_state_directory_unavailable'}
    with receipts._locked(repo, pr, state_dir=state):
        stored = receipts._read_unlocked(repo, pr, state_dir=state)
        intent = stored.get('pending_push') or (stored.get('publication_checkpoint') or {}).get('intent')
        if stored.get('checkpoint_terminal') == 'closed_merged':
            return {'ok': True, 'route': 'recovered', 'reason': 'repair_push_remote_closed'}
        if not intent:
            return {'ok': True, 'route': 'fail_closed', 'reason': 'repair_push_intent_missing'}
        from lokay.proc.probe_pr_state import probe
        identity = probe(repo=repo, pr=pr, live=True, config_path=config_path)
        if (identity.get('ok') is not True or identity.get('probe_failed')
                or identity.get('route') not in {'closed', 'merged'}
                or identity.get('state') not in {'CLOSED', 'MERGED'}
                or identity.get('head_ref') != intent['branch']
                or identity.get('head_repo') != repo
                or identity.get('pr', pr) != pr or identity.get('repo', repo) != repo):
            return {'ok': True, 'route': 'fail_closed', 'reason': 'repair_push_remote_identity_mismatch'}
        stored.update(pending_push=None, closed_push=intent, checkpoint_terminal='closed_merged',
                      closed_remote=identity)
        receipts._write_unlocked(repo, pr, stored, state_dir=state)
    return {'ok': True, 'route': 'recovered', 'reason': 'repair_push_remote_closed',
            'recovery_case': 'closed_merged', 'repo': repo, 'pr': pr}


def retry(*, repo: str, pr: int, config_path: str | None, state_dir: Path) -> dict:
    """Reprobe and revalidate before a non-force exact-SHA push; never count it."""
    try:
        _mutation_gate(config_path)
        observed = reconcile_pending_push(repo=repo, pr=pr, config_path=config_path,
                                          live=True, state_dir=state_dir)
        if observed.get('recovery_case') not in {'pre_attempt', 'remote_unchanged'}:
            return observed
        stored = receipts.read(repo, pr, state_dir=state_dir)
        proof = stored.get('publication_checkpoint')
        if not proof:
            from lokay.proc.pr_repair_checkpoint import recover_legacy
            pending = stored.get('pending_push') or {}
            recovered = recover_legacy(repo=repo, pr=pr, branch=str(pending.get('branch') or ''),
                                       state_dir=state_dir, budget=int(stored.get('budget') or 1))
            if recovered.get('route') != 'checkpointed':
                return {'ok': True, 'route': 'fail_closed', 'reason': 'repair_checkpoint_missing'}
            stored = receipts.read(repo, pr, state_dir=state_dir)
            proof = stored['publication_checkpoint']
            observed = reconcile_pending_push(repo=repo, pr=pr, config_path=config_path,
                                              live=True, state_dir=state_dir)
            if observed.get('recovery_case') not in {'pre_attempt', 'remote_unchanged'}:
                return observed
        verify_local(proof)
        intent = proof['intent']
        with receipts._locked(repo, pr, state_dir=state_dir):
            current = receipts._read_unlocked(repo, pr, state_dir=state_dir)
            if current.get('publication_checkpoint') != proof or current.get('checkpoint_terminal'):
                raise ValueError('checkpoint drift')
            pending = current.get('pending_push')
            if pending is None:
                prepared = receipts._prepare_push_intent_unlocked(
                    repo=repo, pr=pr, intent=intent, budget=int(current.get('budget') or 1), state_dir=state_dir)
                if prepared.get('route') != 'recorded':
                    return prepared
            elif pending['intent_sha256'] != intent['intent_sha256']:
                raise ValueError('pending intent drift')
            if not pending or not pending['push_attempted']:
                marked = receipts._mark_push_attempted_unlocked(
                    repo=repo, pr=pr, intent_sha256=intent['intent_sha256'], state_dir=state_dir)
                if marked.get('route') != 'ready':
                    return marked
            # Serialize retries with receipt writers, retain attempted on every failure.
            verify_local(proof)
            pushed = _push_exact(proof=proof)
        return {'ok': True, 'route': 'retry_pending', 'reason': pushed.get('reason') or 'repair_push_retry_pending',
                'repair_push_intent_sha256': intent['intent_sha256']}
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        return {'ok': True, 'route': 'fail_closed', 'reason': 'repair_retry_unverified', 'detail': str(exc)}
