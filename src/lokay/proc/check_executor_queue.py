"""One configured queue decision after deterministic executor admission."""

import json
from dataclasses import asdict

from lokay.proc.classify_issue_assignee import takeable
from lokay.proc.select_issue_do import leftover_of
from lokay.source import issue_from_task, load_code, load_tasks
from lokay.tasks import TaskId
from lokay.typed_decisions import configured


OFF_GOAL_PARK_AFTER = 3


def _off_goal_streak(path, repo: str, number: int) -> int:
    """Consecutive latest issue_to_pr runs for this issue failing assert_real_diff off_goal."""
    streak = 0
    try:
        lines = open(path, encoding='utf-8').read().splitlines()
    except OSError:
        return 0
    for line in lines:
        if f'"issue": {number}' not in line or '"issue_to_pr"' not in line:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get('kind') != 'issue_to_pr' or event.get('repo') != repo or event.get('issue') != number:
            continue
        off_goal = event.get('delivered') is not True and '"reason": "off_goal"' in str(event.get('steps'))
        streak = streak + 1 if off_goal else 0
    return streak


def check(*, cfg, selected: dict, listed: dict, runner, live: bool) -> dict:
    # Park in lokay state (no labels): N off_goal failures in a row skip the issue.
    if live and cfg.live and _off_goal_streak(cfg.state_path, str(selected['repo']), int(selected['issue'])) >= OFF_GOAL_PARK_AFTER:
        leftover, rows = leftover_of(selected, listed, consume=True)
        return {**selected, 'route': 'skip', 'reason': 'off_goal_parked',
                'leftover': leftover, 'leftover_issues': rows, 'queue_decision': None}
    if not configured(cfg, 'queue_conflict') or not live or not cfg.live:
        return selected
    repo, number = str(selected['repo']), int(selected['issue'])
    reason = 'queue_evidence_unavailable'
    trace = None
    consume = False
    try:
        row = next(row for row in cfg.repos if row.name == repo and row.enabled)
        tasks = load_tasks(row, runner=runner, config=cfg, live=True)
        task = tasks.get(TaskId(tasks.plugin, tasks.target, number))
        if task is not None and str(task.state).upper() == 'OPEN' and takeable(asdict(task), cfg.assignee):
            target = {'repo': repo, 'issue': number,
                      'candidate': issue_from_task(task, repo=repo).to_dict(),
                      'peer_issues': [issue_from_task(peer, repo=repo).to_dict()
                                      for peer in tasks.list_open()],
                      'open_prs': [asdict(pr) for pr in
                                   load_code(row, runner=runner, config=cfg, live=True).pr.list_open()]}
            from lokay.proc.semantic_decision import queue

            result = queue(cfg=cfg, target=target, live=True)
            trace = result['decision_trace']
            if trace['status'] == 'completed' and trace['choice'] == 'ready':
                return {**selected, 'queue_decision': trace}
            # An oversized input fails the same way every pass: park the issue
            # (cursor moves past it) instead of re-picking it forever.
            consume = trace['status'] == 'completed' or trace.get('reason') == 'decision_input_too_large'
            reason = ('decision_' + trace['choice'] if trace['status'] == 'completed' else trace['reason'])
        elif task is not None:
            reason = 'queue_candidate_not_takeable'
    except Exception:
        # No generative fallback or another semantic request on evidence failure.
        reason = 'queue_evidence_unavailable'
    leftover, rows = leftover_of(selected, listed, consume=consume)
    return {**selected, 'route': 'skip', 'reason': reason,
            'leftover': leftover, 'leftover_issues': rows,
            'queue_decision': trace}
