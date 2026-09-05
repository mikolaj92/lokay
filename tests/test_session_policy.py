from pathlib import Path
from lokay.session_policy import resolve_session


def test_builder_first_then_timeout_resume_is_stable_and_harness_neutral(tmp_path: Path):
    first=resolve_session(policy='fresh',repo='a/b',role='builder',issue=7,branch='ai/fix/7',head_sha='abc',base_sha='base')
    resumed=resolve_session(policy='resume',repo='a/b',role='builder',issue=7,branch='ai/fix/7',head_sha='abc',base_sha='base',prior=first)
    assert first['session_id']==resumed['session_id'] and resumed['resolved_policy']=='resume'
    assert 'command' not in resumed and 'transcript' not in resumed


def test_reviewer_is_fresh_and_role_isolated_from_builder():
    builder=resolve_session(policy='fresh',repo='a/b',role='builder',issue=7,branch='x',head_sha='abc',base_sha='base')
    reviewer=resolve_session(policy='fresh',repo='a/b',role='reviewer',issue=7,pr=8,branch='x',head_sha='abc',base_sha='base')
    assert reviewer['session_id'] != builder['session_id'] and reviewer['resolved_policy']=='fresh'


def test_changed_sha_invalidates_resume_but_repair_can_inherit_same_head():
    prior=resolve_session(policy='fresh',repo='a/b',role='builder',issue=7,branch='x',head_sha='abc',base_sha='base')
    changed=resolve_session(policy='resume',repo='a/b',role='builder',issue=7,branch='x',head_sha='def',base_sha='base',prior=prior)
    repair=resolve_session(policy='inherit',repo='a/b',role='repair',issue=7,pr=8,branch='x',head_sha='abc',base_sha='base',prior=prior)
    assert changed['resolved_policy']=='fresh' and changed['reason']=='identity_changed'
    assert repair['source_session_id']==prior['session_id']
