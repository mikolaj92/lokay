from lokay.owner_commands import owner_command


def test_owner_commands():
    assert owner_command('/lokay build please') == 'build'
    assert owner_command('note\n/lokay skip') == 'skip'
    assert owner_command('/lokay retry') == 'retry'
    assert owner_command('just a comment') is None
