"""One configured queue decision after deterministic executor admission."""

from dataclasses import asdict

from lokay.proc.classify_issue_assignee import takeable
from lokay.proc.select_issue_do import leftover_of
from lokay.source import issue_from_task, load_code, load_tasks
from lokay.tasks import TaskId
from lokay.typed_decisions import configured


def check(*, cfg, selected: dict, listed: dict, runner, live: bool) -> dict:
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
            consume = trace['status'] == 'completed'
            reason = ('decision_' + trace['choice'] if consume else trace['reason'])
        elif task is not None:
            reason = 'queue_candidate_not_takeable'
    except Exception:
        # No generative fallback or another semantic request on evidence failure.
        reason = 'queue_evidence_unavailable'
    leftover, rows = leftover_of(selected, listed, consume=consume)
    return {**selected, 'route': 'skip', 'reason': reason,
            'leftover': leftover, 'leftover_issues': rows,
            'queue_decision': trace}
