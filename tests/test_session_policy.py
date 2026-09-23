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


def test_node_session_policy_reaches_the_executor_receipt(tmp_path: Path):
    """The graph's session policy arrives in the harness args and the receipt."""
    import json
    import sys
    from lokay.agent import run_agent
    from lokay.config import Config
    from lokay.runner import Runner

    prior = resolve_session(policy='fresh', repo='o/r', role='builder', issue=7,
                            branch='ai/fix/7', head_sha='abc', base_sha='base')
    script = tmp_path / 'executor.py'
    script.write_text('import sys, pathlib\npathlib.Path("seen.txt").write_text(sys.argv[1])\n')
    cfg = Config(agent='local-executor', agent_command=sys.executable,
                 agent_args=[str(script), '{session}'], executor_enabled=True)
    envelope = run_agent(
        Runner(), cfg, worktree=tmp_path, prompt='edit', execute=True,
        session_kind='code', attach_collector_boundary=False,
        session_policy='resume', session_role='builder', repo='o/r', issue=7,
        branch='ai/fix/7', head_sha='abc', base_sha='base', prior_session=prior,
    )
    assert envelope['status'] == 'completed', envelope
    assert json.loads(envelope['session_receipt'])['resolved_policy'] == 'resume'
    assert (tmp_path / 'seen.txt').read_text() == prior['session_id']
