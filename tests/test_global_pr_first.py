from __future__ import annotations

from lokay.compose import tick


def _config(tmp_path, repos=("a/one", "a/two")):
    path = tmp_path / "config.yaml"
    rows = "\n".join(
        f"  - name: {repo}\n    clone_path: {tmp_path}" for repo in repos
    )
    path.write_text(
        f"""mode: live
repos:
{rows}
executor:
  enabled: true
  command: true
merge:
  enabled: true
  require_checks: false
limits:
  max_triage_per_tick: 0
  max_issues_per_tick: 1
  max_repairs_per_tick: 0
worktrees:
  root: {tmp_path / 'wt'}
state:
  path: {tmp_path / 'state.jsonl'}
"""
    )
    return str(path)


def _pr(number=1, labels=None):
    pr = {
        "number": number,
        "head_ref": f"ai/fix/{number}-x",
        "mergeable": "MERGEABLE",
    }
    if labels is not None:
        pr["labels"] = labels
    return pr


def test_actionable_pr_in_other_repo_blocks_intake(tmp_path, monkeypatch):
    config = _config(tmp_path)

    def fake_run(fn, argv):
        repo = argv[argv.index("--repo") + 1]
        if fn is tick.p_list_prs.main:
            return {"ok": True, "prs": [_pr()] if repo == "a/one" else []}
        if fn is tick.p_list_inbox.main:
            return {"ok": True, "issues": []}
        if fn is tick.p_list_issues.main:
            return {"ok": True, "issues": [{"number": 2, "repo": repo}] if repo == "a/two" else []}
        if fn is tick.p_checks.main:
            return {"ok": True, "status": "pending"}
        raise AssertionError(fn)

    monkeypatch.setattr(tick, "run_preflight", lambda *a, **kw: {"ok": True})
    monkeypatch.setattr(tick, "_run", fake_run)
    monkeypatch.setattr(tick, "compose_issue_to_pr", lambda **_: (_ for _ in ()).throw(AssertionError("intake ran")))
    result = tick.compose_tick(config_path=config, live=True)

    assert result["remaining"]["actionable_open_ai_prs"] == 1
    assert result["remaining"]["manual_open_ai_prs"] == 0
    assert "global PR-first backpressure" in result["remaining"]["intake_skip_reason"]


def test_merge_then_intake_when_global_queue_is_clear(tmp_path, monkeypatch):
    config = _config(tmp_path)

    def fake_run(fn, argv):
        repo = argv[argv.index("--repo") + 1]
        if fn is tick.p_list_prs.main:
            return {"ok": True, "prs": [_pr(labels=[])] if repo == "a/one" else []}
        if fn is tick.p_list_inbox.main:
            return {"ok": True, "issues": []}
        if fn is tick.p_list_issues.main:
            return {"ok": True, "issues": [{"number": 2, "repo": repo, "title": "next"}] if repo == "a/two" else []}
        if fn is tick.p_checks.main:
            return {"ok": True, "status": "none", "merge_ok": True}
        raise AssertionError(fn)

    intake = []
    monkeypatch.setattr(tick, "run_preflight", lambda *a, **kw: {"ok": True})
    monkeypatch.setattr(tick, "_run", fake_run)
    monkeypatch.setattr(tick, "compose_pr_triage", lambda **_: {"ok": True, "merged": True})
    monkeypatch.setattr(tick, "compose_issue_to_pr", lambda **kw: intake.append(kw) or {"ok": True, "pr": 2, "branch": "ai/fix/2-next"})
    result = tick.compose_tick(config_path=config, live=True)

    assert len(intake) == 1
    assert intake[0]["repo"] == "a/two"
    assert result["remaining"]["intake_skip_reason"] is None


def test_manual_only_pr_allows_unrelated_repo_intake(tmp_path, monkeypatch):
    config = _config(tmp_path)

    def fake_run(fn, argv):
        repo = argv[argv.index("--repo") + 1]
        if fn is tick.p_list_prs.main:
            return {"ok": True, "prs": [_pr(labels=["ai:needs-review"])] if repo == "a/one" else []}
        if fn is tick.p_list_inbox.main:
            return {"ok": True, "issues": []}
        if fn is tick.p_list_issues.main:
            return {"ok": True, "issues": [{"number": 2, "repo": repo, "title": "next"}]}
        raise AssertionError(fn)

    intake = []
    monkeypatch.setattr(tick, "run_preflight", lambda *a, **kw: {"ok": True})
    monkeypatch.setattr(tick, "_run", fake_run)
    monkeypatch.setattr(tick, "compose_issue_to_pr", lambda **kw: intake.append(kw) or {"ok": True, "pr": 2, "branch": "ai/fix/2-next"})
    result = tick.compose_tick(config_path=config, live=True)

    assert len(intake) == 1
    assert intake[0]["repo"] == "a/two"
    assert result["remaining"]["open_ai_prs"] == 2
    assert result["remaining"]["actionable_open_ai_prs"] == 1  # newly opened PR
    assert result["remaining"]["manual_open_ai_prs"] == 1
    assert result["remaining"]["intake_skip_reason"] is None


def test_malformed_labels_fail_closed(tmp_path, monkeypatch):
    config = _config(tmp_path)

    def fake_run(fn, argv):
        repo = argv[argv.index("--repo") + 1]
        if fn is tick.p_list_prs.main:
            return {"ok": True, "prs": [_pr(labels={"name": "ai:needs-review"})] if repo == "a/one" else []}
        if fn in {tick.p_list_inbox.main, tick.p_list_issues.main}:
            return {"ok": True, "issues": []}
        if fn is tick.p_checks.main:
            return {"ok": True, "status": "pending"}
        raise AssertionError(fn)

    monkeypatch.setattr(tick, "run_preflight", lambda *a, **kw: {"ok": True})
    monkeypatch.setattr(tick, "_run", fake_run)
    result = tick.compose_tick(config_path=config, live=True)
    assert result["remaining"]["actionable_open_ai_prs"] == 1
    assert result["remaining"]["manual_open_ai_prs"] == 0


def test_pr_survey_failure_blocks_triage_and_intake(tmp_path, monkeypatch):
    config = _config(tmp_path)
    triage = []

    def fake_run(fn, argv):
        repo = argv[argv.index("--repo") + 1]
        if fn is tick.p_list_prs.main:
            return {"ok": False, "error": "boom"} if repo == "a/one" else {"ok": True, "prs": []}
        if fn is tick.p_list_inbox.main:
            return {"ok": True, "issues": [{"number": 3, "repo": repo}]}
        if fn is tick.p_list_issues.main:
            return {"ok": True, "issues": [{"number": 2, "repo": repo, "title": "next"}]}
        raise AssertionError(fn)

    monkeypatch.setattr(tick, "run_preflight", lambda *a, **kw: {"ok": True})
    monkeypatch.setattr(tick, "_run", fake_run)
    monkeypatch.setattr(tick, "run_path", lambda **kw: triage.append(kw))
    monkeypatch.setattr(tick, "compose_issue_to_pr", lambda **_: (_ for _ in ()).throw(AssertionError("intake ran")))
    result = tick.compose_tick(config_path=config, live=True)
    assert triage == []
    assert result["remaining"]["survey_errors"] == 1
    assert "survey failed closed" in result["remaining"]["intake_skip_reason"]


def test_needs_human_discovered_this_pass_becomes_manual(tmp_path, monkeypatch):
    config = _config(tmp_path)

    def fake_run(fn, argv):
        repo = argv[argv.index("--repo") + 1]
        if fn is tick.p_list_prs.main:
            return {"ok": True, "prs": [_pr(labels=[])] if repo == "a/one" else []}
        if fn is tick.p_list_inbox.main:
            return {"ok": True, "issues": []}
        if fn is tick.p_list_issues.main:
            return {"ok": True, "issues": [{"number": 2, "repo": repo, "title": "next"}] if repo == "a/two" else []}
        if fn is tick.p_checks.main:
            return {"ok": True, "status": "none", "merge_ok": True}
        raise AssertionError(fn)

    intake = []
    monkeypatch.setattr(tick, "run_preflight", lambda *a, **kw: {"ok": True})
    monkeypatch.setattr(tick, "_run", fake_run)
    monkeypatch.setattr(tick, "compose_pr_triage", lambda **_: {
        "ok": True, "skipped": True, "repairable": False,
        "review": {"verdict": "needs_human", "secrets": False},
    })
    monkeypatch.setattr(tick, "compose_issue_to_pr", lambda **kw: intake.append(kw) or {"ok": True, "pr": 2, "branch": "ai/fix/2-next"})
    result = tick.compose_tick(config_path=config, live=True)
    assert len(intake) == 1
    assert intake[0]["repo"] == "a/two"
    assert result["remaining"]["manual_open_ai_prs"] == 1
