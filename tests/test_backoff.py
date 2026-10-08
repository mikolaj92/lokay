from lokay.failure import repo_backoff_seconds


def test_backoff_schedule():
    assert [repo_backoff_seconds(n) for n in (1, 3, 4, 5, 20)] == [0, 60, 120, 240, 6 * 60 * 60]
