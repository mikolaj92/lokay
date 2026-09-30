from lokay.proc.summarize_pr_triage_department import summarize
from lokay.proc.select_next_pr import select


def test_fleet_repair_keeps_identity_but_yields_next_slot():
    picked = {'route': 'pr', 'repo': 'o/sqlite', 'pr': 28, 'branch': 'ai/fix/22', 'head_sha': 'a'*40,
              'leftover_prs': [{'repo': 'o/punk', 'pr': 43, 'branch': 'ai/fix/35', 'head_sha': 'b'*40}]}
    receipt = summarize(picked, {}, {'route': 'completed', 'verdict': 'repair', 'repairable': True},
                        {'route': 'review'}, incomplete_retry_position='tail')
    live = [{k:v for k,v in picked.items() if k in ('repo','pr','branch','head_sha')}, *picked['leftover_prs']]
    live[0]['head_sha'] = 'c'*40  # published repair is still KEEP, not lost
    next_pr = select({'prs': live}, receipt)
    assert next_pr['repo'] == 'o/punk'
    assert next_pr['leftover_prs'][0]['head_sha'] == 'c'*40
    assert len(receipt['leftover_prs']) == 2
