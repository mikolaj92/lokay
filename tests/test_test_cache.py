from lokay.blueprint_test_cache import remember_test


def test_same_sha_and_argv_run_once():
    calls = []
    def run():
        calls.append(1)
        return {"exit": 0, "digest": "ok"}
    cache = {}
    first = remember_test(cache, head_sha="abc", argv=["pytest"], run=run)
    second = remember_test(cache, head_sha="abc", argv=["pytest"], run=run)
    assert first["ran"] is True
    assert second["cached"] is True
    assert calls == [1]


def test_a_different_argv_runs_again():
    calls = []
    def run():
        calls.append(1)
        return {"exit": 1, "digest": "no"}
    cache = {}
    remember_test(cache, head_sha="abc", argv=["pytest"], run=run)
    remember_test(cache, head_sha="abc", argv=["pytest", "tests"], run=run)
    assert len(calls) == 2
