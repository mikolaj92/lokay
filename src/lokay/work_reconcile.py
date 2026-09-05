"""Pure observe-first reducer for one work unit."""
from __future__ import annotations
from typing import Any

def reconcile_work(facts: dict[str,Any])->dict[str,Any]:
    if facts.get('issue_read')!='ok': return {'state':'unknown','route':'survey_error','effect':None,'reason':'authoritative_read_failed'}
    if facts.get('merged_sha'):
        return {'state':'delivered','route':'delivered','effect':None,'evidence':{'merged_sha':facts['merged_sha'],'pr':facts.get('covering_pr')}}
    if facts.get('covering_pr'):
        return {'state':'pr_open','route':'continue','effect':None,'evidence':{'pr':facts['covering_pr'],'head_sha':facts.get('head_sha')}}
    if facts.get('worktree')=='dirty': return {'state':'implementing','route':'resume','effect':'resume_worker'}
    if facts.get('branch_exists') is False: return {'state':'repairable','route':'repair','effect':'restore_branch'}
    if facts.get('live_process'): return {'state':'implementing','route':'continue','effect':None}
    if facts.get('issue_state')=='closed': return {'state':'terminal_conflict','route':'terminal_conflict','effect':None,'reason':'closed_without_merge'}
    return {'state':'ready','route':'continue','effect':None}
