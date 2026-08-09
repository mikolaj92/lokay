from lokay.compose import pr_triage


def test_triage_always_runs_fala(monkeypatch):
    seen = {}
    def fake_run(**kwargs):
        seen.update(kwargs)
        return {"ok": True, "skipped": True, "reason": "llm_review_requested_changes", "repairable": True, "review": {"verdict": "request_changes"}}
    monkeypatch.setattr(pr_triage, "run_path", fake_run)
    out = pr_triage.compose_pr_triage(config_path=None, repo="a/b", pr_number=9, branch="ai/fix/9-x", live=False)
    assert seen["path_id"] == "pr_triage"
    assert out["engine"] == "fala"
    assert out["repairable"] is True
