from pathlib import Path
from lokay.capabilities import executor_environment,authorize_effect

def test_builder_has_code_write_but_no_merge_or_acceptance_write(tmp_path:Path):
 env=executor_environment('builder',{'GH_TOKEN':'secret','LOKAY_HEALTH_LEASE':'lease','PATH':'/bin'})
 assert env=={'PATH':'/bin','LOKAY_CAPABILITIES':'code.write'}
 assert not authorize_effect('builder','pr.merge')['allowed'] and not authorize_effect('builder','acceptance.write')['allowed']
def test_reviewer_is_read_only_and_cannot_push_or_rewrite_verdict():
 assert executor_environment('reviewer',{'GH_TOKEN':'x'})=={'LOKAY_CAPABILITIES':'evidence.read,verdict.propose'}
 assert not authorize_effect('reviewer','git.push')['allowed'] and not authorize_effect('reviewer','verdict.rewrite')['allowed']
def test_dedicated_effect_gets_only_authored_authority_and_denial_is_traceable():
 assert authorize_effect('merge_effect','pr.merge')['allowed']
 denied=authorize_effect('reviewer','pr.merge')
 assert denied=={'allowed':False,'route':'fail_closed','reason':'capability_denied','role':'reviewer','capability':'pr.merge','trace':True}
