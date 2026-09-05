import json,tomllib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def test_authored_survey_uses_bounded_template_not_manual_slots():
 text=(ROOT/'fala/lokay.fala-package.toml').read_text();package=tomllib.loads(text)
 path=next(p for p in package['correlation_paths'] if p['id']=='survey_prs')
 assert 'effectors' not in path and path['expansion']['max_items']==30 and path['expansion']['serial'] is True
 assert 'select_pr_survey_repo_1"' not in text and 'select_pr_survey_repo_30"' not in text
def test_golden_expansion_keeps_every_slot_and_edges():
 package=json.loads((ROOT/'fala/lokay.expanded.golden.json').read_text());path=next(p for p in package['correlation_paths'] if p['id']=='survey_prs');ids=[e['id'] for e in path['effectors']]
 assert len(ids)==124 and ids[:2]==['prepare_pr_survey','select_pr_survey_repo_1'] and ids[-4:]==['record_pr_survey_repo_30','reduce_pr_survey','persist_pr_survey','update_pr_survey_stamp']
 for i in range(2,31):
  e=next(x for x in path['effectors'] if x['id']==f'select_pr_survey_repo_{i}')
  assert f'record_pr_survey_repo_{i-1}' in e['conduction']
