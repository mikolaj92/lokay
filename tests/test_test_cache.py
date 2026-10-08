from lokay.test_cache import cached_test


def test_same_sha_and_argv_run_once():
    calls = []
    def run():
        calls.append(1)
        return {"exit": 0, "digest": "ok"}
    cache = {}
    first = cached_test(cache, head_sha="abc", argv=["pytest"], run=run)
    second = cached_test(cache, head_sha="abc", argv=["pytest"], run=run)
    assert first["ran"] is True
    assert second["cached"] is True
    assert calls == [1]


def test_a_different_argv_runs_again():
    calls = []
    def run():
        calls.append(1)
        return {"exit": 1, "digest": "no"}
    cache = {}
    cached_test(cache, head_sha="abc", argv=["pytest"], run=run)
    cached_test(cache, head_sha="abc", argv=["pytest", "tests"], run=run)
    assert len(calls) == 2
