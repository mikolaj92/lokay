from lokay.push_guard import push_allowed


def test_absent_remote_may_be_pushed():
    assert push_allowed(remote_sha="", expected_sha="abc") is True


def test_matching_remote_may_be_pushed():
    assert push_allowed(remote_sha="abc", expected_sha="abc") is True


def test_a_moved_remote_is_refused():
    assert push_allowed(remote_sha="def", expected_sha="abc") is False
