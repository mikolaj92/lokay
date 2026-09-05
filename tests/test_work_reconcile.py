from lokay.work_reconcile import reconcile_work

BASE={'issue_read':'ok','issue_state':'open','covering_pr':None,'branch_exists':True,'head_sha':'h','base_sha':'b','merged_sha':None,'live_process':False,'worktree':'clean','journal_ref':'j'}

def test_merged_world_wins_over_stale_receipt_and_replay_is_idempotent():
    facts={**BASE,'issue_state':'closed','covering_pr':7,'merged_sha':'m','receipt':{'reason':'condition_not_met'}}
    assert reconcile_work(facts)==reconcile_work(facts)=={'state':'delivered','route':'delivered','effect':None,'evidence':{'merged_sha':'m','pr':7}}

def test_unreadable_world_is_unknown_and_never_cleanup():
    out=reconcile_work({**BASE,'issue_read':'error'})
    assert out['state']=='unknown' and out['route']=='survey_error' and out['effect'] is None

def test_one_route_for_orphan_dirty_deleted_and_crash_after_push():
    assert reconcile_work({**BASE,'covering_pr':7,'live_process':False})['route']=='continue'
    assert reconcile_work({**BASE,'worktree':'dirty'})['route']=='resume'
    assert reconcile_work({**BASE,'branch_exists':False})['route']=='repair'
    pushed=reconcile_work({**BASE,'covering_pr':7,'receipt':{'phase':'pushing'}})
    assert pushed['route']=='continue' and pushed['effect'] is None
