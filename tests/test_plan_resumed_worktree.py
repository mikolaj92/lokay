from lokay.proc.build_issue_approach import build


def test_plan_prompt_explains_resumed_unpublished_diff(tmp_path):
    def execute(prompt):
        assert 'unpublished implementation' in prompt
        assert 'git status and diff' in prompt
        return {'status': 'completed', 'result_stdout': '{"ok":true,"goal":"verify existing fix","files":["src/code.py"],"test_plan":["pytest"],"non_goals":[],"test_command":"pytest"}'}
    result = build({'worktree': str(tmp_path), 'issue': {'repo': 'o/r', 'number': 1, 'title': 'Fix code', 'body': 'Keep the implementation'}, 'rel_path': '.lokay/approach.md'}, execute=execute)
    assert result['ok'] is True
