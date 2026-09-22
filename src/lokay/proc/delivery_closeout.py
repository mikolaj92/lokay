"""Durable closeout evidence in the existing ledger, not a second scheduler."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from lokay.code.pr import require_head_sha
from lokay.state import append_event


def _digest(intent: dict) -> str:
    return hashlib.sha256(json.dumps({k: v for k, v in intent.items() if k != 'sha256'},
                                    sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def validate(intent: dict) -> dict:
    if (intent.get('schema') != 'lokay.delivery-closeout/1'
            or not intent.get('repo') or not intent.get('branch')
            or type(intent.get('pr')) is not int or intent['pr'] < 1
            or type(intent.get('issue')) is not int or intent['issue'] < 1
            or intent.get('sha256') != _digest(intent)):
        raise ValueError('delivery_closeout_identity_invalid')
    head = require_head_sha(intent.get('head_sha'))
    if ((intent.get('review', {}).get('decision') or {}).get('reviewed_head_sha') != head
            or intent['review']['decision'].get('verdict') != 'approve'
            or intent.get('tests', {}).get('tested_head_sha') != head
            or intent['tests'].get('ok') is not True or intent['tests'].get('passed') is False):
        raise ValueError('delivery_closeout_evidence_invalid')
    return intent


def prepare(*, state_path: Path, repo: str, pr: int, issue: int, branch: str,
            review: dict, tests: dict, live: bool, keep_issue_open: bool = False) -> dict:
    if not live:
        return {'ok': True, 'route': 'ready', 'planned': True}
    try:
        intent = {'schema': 'lokay.delivery-closeout/1', 'repo': repo, 'pr': pr,
                  'issue': issue, 'branch': branch,
                  'head_sha': (review.get('decision') or {}).get('reviewed_head_sha'),
                  'review': review, 'tests': tests, 'keep_issue_open': keep_issue_open}
        intent['sha256'] = _digest(intent)
        validate(intent)
        append_event(state_path, {'kind': 'delivery_closeout_intent', 'repo': repo,
                                 'pr': pr, 'issue': issue, 'intent': intent}, durable=True)
        return {'ok': True, 'route': 'ready', 'intent': intent}
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return {'ok': True, 'route': 'pending', 'reason': 'delivery_closeout_intent_failed',
                'detail': str(exc)}


def pending(state_path: Path) -> list[dict]:
    """Read outstanding intentions, including PRs absent from the open list."""
    if not state_path.exists():
        return []
    intents: dict[tuple, dict] = {}
    completed = set()
    with state_path.open() as stream:
        for line in stream:
            try:
                event = json.loads(line)
                if event.get('kind') == 'delivery_closeout_complete':
                    completed.add(event['intent_sha256'])
                elif event.get('kind') == 'delivery_closeout_intent':
                    intent = validate(event['intent'])
                    intents[(intent['repo'], intent['pr'])] = intent
            except (ValueError, TypeError, KeyError, AttributeError):
                # A damaged unrelated event cannot pin the entire PR queue.
                continue
    return [dict(intent) for intent in intents.values() if intent['sha256'] not in completed]


def complete(state_path: Path, intent: dict) -> None:
    validate(intent)
    append_event(state_path, {'kind': 'delivery_closeout_complete',
                             'repo': intent['repo'], 'pr': intent['pr'],
                             'intent_sha256': intent['sha256']}, durable=True)


def observe(*, picked: dict, config_path: str | None, live: bool) -> dict:
    if not picked.get('delivery_replay'):
        return {'ok': True, 'route': 'review'}
    if not live:
        return {'ok': True, 'route': 'pending', 'reason': 'delivery_closeout_planned'}
    try:
        from lokay.config import load_config
        from lokay.gh_prs import gh_json, gh_text
        from lokay.proc._common import runner
        intent = validate(picked['closeout_intent'])
        if intent.get('keep_issue_open'):
            return {'ok': True, 'route': 'pending', 'reason': 'delivery_keep_issue_open'}
        if any(picked.get(key) != intent[key] for key in ('repo', 'pr', 'branch', 'head_sha')):
            raise ValueError('delivery_closeout_identity_mismatch')
        carrier = runner(load_config(config_path))
        viewed = gh_json(carrier, ['pr', 'view', str(intent['pr']), '--repo', intent['repo'],
            '--json', 'headRefOid,headRefName,headRepository,baseRefName,state,mergeCommit,mergedAt'], live=True)
        if (viewed.get('headRefOid') != intent['head_sha']
                or viewed.get('headRefName') != intent['branch']
                or (viewed.get('headRepository') or {}).get('nameWithOwner') != intent['repo']
                or viewed.get('baseRefName') != 'main'):
            raise ValueError('delivery_closeout_identity_mismatch')
        if viewed.get('state') == 'OPEN' and not viewed.get('mergedAt'):
            return {'ok': True, 'route': 'review'}
        if (viewed.get('state') != 'MERGED' or not viewed.get('mergedAt')
                or not (viewed.get('mergeCommit') or {}).get('oid')):
            raise ValueError('delivery_merge_unconfirmed')
        status = gh_text(carrier, ['api', f"repos/{intent['repo']}/compare/{intent['head_sha']}...main",
                                  '--jq', '.status'], live=True, require_success=True).strip()
        if status not in {'ahead', 'identical'}:
            raise ValueError('delivery_main_unconfirmed')
        return {'ok': True, 'route': 'close', 'merged': True, 'intent': intent}
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        reason = str(exc) if str(exc).startswith('delivery_') else 'delivery_observation_failed'
        return {'ok': True, 'route': 'pending', 'reason': reason}


def close(*, picked: dict, config_path: str | None, live: bool) -> dict:
    # Re-read at the effect boundary; prior observation is not mutation authority.
    observed = observe(picked=picked, config_path=config_path, live=live)
    if observed['route'] != 'close':
        return observed
    try:
        from lokay.config import load_config
        from lokay.gh_prs import gh_json, gh_text
        from lokay.proc._common import mutations_allowed, runner
        intent = observed['intent']
        cfg = load_config(config_path)
        carrier = runner(cfg)
        issue = gh_json(carrier, ['issue', 'view', str(intent['issue']), '--repo', intent['repo'],
                                 '--json', 'state'], live=True)
        if issue.get('state') != 'CLOSED':
            if issue.get('state') != 'OPEN':
                raise ValueError('delivery_issue_state_unavailable')
            if not mutations_allowed(live_flag=live, cfg=cfg):
                raise ValueError('delivery_close_unauthorized')
            gh_text(carrier, ['issue', 'close', str(intent['issue']), '--repo', intent['repo']],
                    live=True, require_success=True)
        return {**observed, 'route': 'publish', 'issue_closed': True, 'closed_issue': intent['issue']}
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        return {**observed, 'route': 'pending', 'reason': 'delivery_close_failed', 'detail': str(exc)}


def publish(*, picked: dict, config_path: str | None, live: bool) -> dict:
    observed = observe(picked=picked, config_path=config_path, live=live)
    if observed['route'] != 'close':
        return observed
    from lokay.config import load_config
    from lokay.proc.publish_delivery_receipt import publish_from_config
    intent = observed['intent']
    result = publish_from_config(
        config_path=config_path, live=live, closeout_intent=intent,
        repo=intent['repo'], pr=intent['pr'], issue=intent['issue'],
        merge={'merged': True}, close={}, review=intent['review'], tests=intent['tests'],
    )
    if result.get('confirmed'):
        try:
            complete(load_config(config_path).state_path, intent)
        except (OSError, ValueError) as exc:
            return {**observed, 'route': 'pending', 'reason': 'delivery_completion_record_failed', 'detail': str(exc)}
    return {**observed, **result}


def triage(observed: dict, closed: dict, published: dict) -> dict:
    result = next((value for value in (published, closed, observed) if value.get('route')), observed)
    intent = observed.get('intent') or {}
    issue_closed = result.get('issue_closed', closed.get('issue_closed')) is True
    return {'ok': True, 'route': 'completed', 'triage': {
        'merged': observed.get('merged') is True, 'repairable': False,
        'delivery_confirmed': result.get('confirmed') is True,
        'delivery_receipt': dict(result.get('receipt') or {}),
        'issue_closed': issue_closed,
        'closed_issue': intent.get('issue', 0) if issue_closed else 0,
        'waiting': result.get('confirmed') is not True,
        'reason': result.get('reason') or ('delivery_confirmed' if result.get('confirmed') else 'delivery_closeout_pending'),
    }}
