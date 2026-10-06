from lokay.preflight import acquire_run_lock, issue_health_lease


def _parent_capability(tmp_path, monkeypatch):
    from pr_first_fixtures import empty_pr_survey

    empty_pr_survey(tmp_path, monkeypatch)
    monkeypatch.setenv("HOME", str(tmp_path))
    lock = tmp_path / ".lokay" / "lokay.lock"
    assert acquire_run_lock(lock)
    issue_health_lease(lock_path=lock)
