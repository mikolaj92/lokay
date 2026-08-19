from lokay.proc import detach_issue_to_pr as detach


def test_product_repo_is_skipped_before_any_side_effect(monkeypatch):
    def unexpected(*_args, **_kwargs):
        raise AssertionError("foreign repo must not spawn or write")

    monkeypatch.setattr(detach.subprocess, "Popen", unexpected)
    monkeypatch.setattr(detach, "issue_to_pr_log_path", unexpected)
    monkeypatch.setattr(detach, "write_issue_to_pr_receipt", unexpected)

    result = detach.detach_issue_to_pr(
        repo="mikolaj92/Temida",
        issue=550,
        config_path="config.yaml",
    )

    assert result == {
        "ok": True,
        "detached": False,
        "skipped": True,
        "reason": "repo_not_delivered_by_mini_mill",
        "repo": "mikolaj92/Temida",
        "issue": 550,
    }


def test_mini_mill_repo_still_spawns(monkeypatch, tmp_path):
    calls = []

    class FakePopen:
        def __init__(self, argv, **kwargs):
            calls.append((argv, kwargs))
            self.pid = 4242

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("LOKAY_PROCESS_HEAD", "a" * 40)
    monkeypatch.setenv("LOKAY_HEALTH_LEASE", "b" * 64)
    monkeypatch.setenv(
        "LOKAY_HEALTH_LEASE_PATH", str(tmp_path / ".lokay" / "health-lease")
    )

    result = detach.detach_issue_to_pr(
        repo=detach.MINI_MILL_REPO,
        issue=550,
        config_path=None,
        popen=FakePopen,
    )

    assert result["ok"] is True
    assert result["detached"] is True
    assert result["repo"] == detach.MINI_MILL_REPO
    assert len(calls) == 1
