from datetime import datetime,timezone
from lokay.github_yield import catalog_delivery

class Runner:
 def __init__(self,rows):self.rows=rows
 def run_checked(self,spec,live=True):
  import json,types,re
  repo=re.search(r'repos/([^/]+/[^/]+)/pulls', ' '.join(spec.argv)).group(1)
  return types.SimpleNamespace(stdout=json.dumps(self.rows.get(repo,[])))

def test_catalog_totals_equal_repos_and_manual_is_unattributed():
 auto={'merged_at':'2026-09-05T00:00:00Z','created_at':'2026-09-04T23:00:00Z','body':'<!-- lokay-autonomous-delivery:{"marker":true} -->'}
 manual={**auto,'body':'manual'}
 out=catalog_delivery(Runner({'a/one':[auto,manual],'b/two':[]}),['a/one','b/two'],since=datetime(2026,9,4,tzinfo=timezone.utc),hours=24,receipt_detector=lambda body:'autonomous' if 'lokay-autonomous' in body else 'unattributed')
 assert set(out['repos'])=={'a/one','b/two'}
 assert out['totals']=={'merged':2,'autonomous':1,'unattributed':1,'read_errors':0}
 assert sum(r['autonomous'] for r in out['repos'].values())==out['totals']['autonomous']
