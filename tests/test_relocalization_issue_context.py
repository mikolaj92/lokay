from lokay.git_real_diff import is_disposable_ignored_path
from lokay.organ.relocalize_boundary import handle_relocalize
from lokay.proc.build_relocalization_agent_request import build


def test_relocalization_receives_issue_and_diff_goal(tmp_path):
    import json
    (tmp_path / '.lokay').mkdir()
    (tmp_path / '.lokay/localize.json').write_text(json.dumps({'paths': ['src/sqlite.mojo']}))
    issue = {'title': 'Rename datatype constants', 'body': 'Migrate all datatype callers; keep result codes unchanged.'}
    evidence = handle_relocalize('inspect_relocalization_evidence',
        {'worktree': str(tmp_path), 'issue_raw': issue}, {}, {})
    prompt = build(evidence, {'route': 'agent', 'off_goal_paths': ['tests/types.mojo']})['prompt']
    assert issue['title'] in prompt
    assert issue['body'] in prompt
    assert 'tests/types.mojo' in prompt


def test_pixi_environment_is_disposable_not_scope_evidence():
    assert is_disposable_ignored_path('.pixi/envs/default/lib/libsqlite3.dylib')
    assert not is_disposable_ignored_path('src/sqlite.mojo')
