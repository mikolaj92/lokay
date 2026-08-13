"""Per-repo PR-first: actionable AI PRs freeze only their own repository."""

from __future__ import annotations

from lokay.compose import tick


def _intake_ok():
    return {
        "ok": True,
        "implementable": True,
        "applied": False,
        "decision": {"decision": "ready", "reason": "intake_ok"},
    }


def _config(tmp_path, repos=("a/one", "a/two"), **limit_overrides):
    path = tmp_path / "config.yaml"
    rows = "\n".join(
        f"  - name: {repo}\n    clone_path: {tmp_path}" for repo in repos
    )
    limits = {
        "max_triage_per_tick": 0,
        "max_issue_to_pr_per_pass": 1,
        "max_repairs_per_tick": 0,
        **limit_overrides,
    }
    lim_yaml = "\n".join(f"  {k}: {v}" for k, v in limits.items())
    path.write_text(
        f"""mode: live
repos:
{rows}
executor:
  enabled: true
  command: true
  args: ["{{prompt}}"]
merge:
  enabled: true
  require_checks: false
limits:
{lim_yaml}
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


def test_actionable_pr_in_other_repo_allows_intake(tmp_path, monkeypatch):
    """Stuck/busy repo A must not block ready repo B (replaces global freeze)."""
    config = _config(tmp_path)

    def fake_run(fn, argv):
        repo = argv[argv.index("--repo") + 1]
        if fn is tick.p_list_prs.main:
            return {"ok": True, "prs": [_pr()] if repo == "a/one" else []}
        if fn is tick.p_list_inbox.main:
            return {"ok": True, "issues": []}
        if fn is tick.p_list_issues.main:
            return {
                "ok": True,
                "issues": [{"number": 2, "repo": repo, "title": "next"}]
                if repo == "a/two"
                else [],
            }
        if fn is tick.p_checks.main:
            return {"ok": True, "status": "pending"}
        if fn is tick.p_intake.main:
            return _intake_ok()
        raise AssertionError(fn)

    intake = []
    monkeypatch.setattr(tick, "run_preflight", lambda *a, **kw: {"ok": True})
    monkeypatch.setattr(tick, "_run", fake_run)
    monkeypatch.setattr(
        tick,
        "compose_issue_to_pr",
        lambda **kw: intake.append(kw) or {"ok": True, "pr": 2, "branch": "ai/fix/2-next"},
    )
    result = tick.compose_tick(config_path=config, live=True)

    assert len(intake) == 1
    assert intake[0]["repo"] == "a/two"
    assert result["remaining"]["actionable_open_ai_prs"] == 2  # pending + new
    assert result["remaining"]["manual_open_ai_prs"] == 0
    assert result["remaining"]["intake_skip_reason"] is None
    assert any(
        a.get("step") == "skip_ready_open_ai_pr" and a.get("repo") == "a/one"
        for a in result["actions"]
    )


def test_actionable_pr_blocks_same_repo_intake_and_triage(tmp_path, monkeypatch):
    config = _config(tmp_path, repos=("a/one",), max_triage_per_tick=5)
    triage = []

    def fake_run(fn, argv):
        if fn is tick.p_list_prs.main:
            return {"ok": True, "prs": [_pr()]}
        if fn is tick.p_list_inbox.main:
            return {"ok": True, "issues": [{"number": 3, "repo": "a/one"}]}
        if fn is tick.p_list_issues.main:
            return {
                "ok": True,
                "issues": [{"number": 2, "repo": "a/one", "title": "next"}],
            }
        if fn is tick.p_checks.main:
            return {"ok": True, "status": "pending"}
        raise AssertionError(fn)

    monkeypatch.setattr(tick, "run_preflight", lambda *a, **kw: {"ok": True})
    monkeypatch.setattr(tick, "_run", fake_run)
    monkeypatch.setattr(tick, "run_path", lambda **kw: triage.append(kw) or {"ok": True})
    monkeypatch.setattr(
        tick,
        "compose_issue_to_pr",
        lambda **_: (_ for _ in ()).throw(AssertionError("intake ran")),
    )
    result = tick.compose_tick(config_path=config, live=True)

    assert triage == []
    assert any(
        a.get("step") == "skip_inbox_triage_repo_backpressure" for a in result["actions"]
    )
    assert any(a.get("step") == "skip_ready_open_ai_pr" for a in result["actions"])
    assert result["remaining"]["intake_skip_reason"] is None


def test_merge_then_intake_when_repo_queue_is_clear(tmp_path, monkeypatch):
    config = _config(tmp_path)

    def fake_run(fn, argv):
        repo = argv[argv.index("--repo") + 1]
        if fn is tick.p_list_prs.main:
            return {"ok": True, "prs": [_pr(labels=[])] if repo == "a/one" else []}
        if fn is tick.p_list_inbox.main:
            return {"ok": True, "issues": []}
        if fn is tick.p_list_issues.main:
            return {
                "ok": True,
                "issues": [{"number": 2, "repo": repo, "title": "next"}]
                if repo == "a/two"
                else [],
            }
        if fn is tick.p_checks.main:
            return {"ok": True, "status": "none", "merge_ok": True}
        if fn is tick.p_intake.main:
            return _intake_ok()
        raise AssertionError(fn)

    intake = []
    monkeypatch.setattr(tick, "run_preflight", lambda *a, **kw: {"ok": True})
    monkeypatch.setattr(tick, "_run", fake_run)
    monkeypatch.setattr(tick, "compose_pr_triage", lambda **_: {"ok": True, "merged": True})
    monkeypatch.setattr(
        tick,
        "compose_issue_to_pr",
        lambda **kw: intake.append(kw) or {"ok": True, "pr": 2, "branch": "ai/fix/2-next"},
    )
    result = tick.compose_tick(config_path=config, live=True)

    assert len(intake) == 1
    assert intake[0]["repo"] == "a/two"
    assert result["remaining"]["intake_skip_reason"] is None


def test_manual_only_pr_allows_unrelated_repo_intake(tmp_path, monkeypatch):
    config = _config(tmp_path)

    def fake_run(fn, argv):
        repo = argv[argv.index("--repo") + 1]
        if fn is tick.p_list_prs.main:
            return {
                "ok": True,
                "prs": [_pr(labels=["ai:needs-review"])] if repo == "a/one" else [],
            }
        if fn is tick.p_list_inbox.main:
            return {"ok": True, "issues": []}
        if fn is tick.p_list_issues.main:
            return {
                "ok": True,
                "issues": [{"number": 2, "repo": repo, "title": "next"}]
                if repo == "a/two"
                else [],
            }
        if fn is tick.p_intake.main:
            return _intake_ok()
        raise AssertionError(fn)

    intake = []
    monkeypatch.setattr(tick, "run_preflight", lambda *a, **kw: {"ok": True})
    monkeypatch.setattr(tick, "_run", fake_run)
    monkeypatch.setattr(
        tick,
        "compose_issue_to_pr",
        lambda **kw: intake.append(kw) or {"ok": True, "pr": 2, "branch": "ai/fix/2-next"},
    )
    result = tick.compose_tick(config_path=config, live=True)

    assert len(intake) == 1
    assert intake[0]["repo"] == "a/two"
    assert result["remaining"]["open_ai_prs"] == 2
    assert result["remaining"]["actionable_open_ai_prs"] == 1  # newly opened PR
    assert result["remaining"]["manual_open_ai_prs"] == 1
    assert result["remaining"]["intake_skip_reason"] is None


def test_manual_only_pr_does_not_block_same_repo_intake(tmp_path, monkeypatch):
    """Parked human work must not stall intentional ready work in that repo."""
    config = _config(tmp_path, repos=("a/one",))

    def fake_run(fn, argv):
        repo = argv[argv.index("--repo") + 1]
        if fn is tick.p_list_prs.main:
            return {"ok": True, "prs": [_pr(labels=["ai:needs-review"])]}
        if fn is tick.p_list_inbox.main:
            return {"ok": True, "issues": []}
        if fn is tick.p_list_issues.main:
            return {
                "ok": True,
                "issues": [{"number": 2, "repo": repo, "title": "next"}],
            }
        if fn is tick.p_intake.main:
            return _intake_ok()
        raise AssertionError(fn)

    intake = []
    monkeypatch.setattr(tick, "run_preflight", lambda *a, **kw: {"ok": True})
    monkeypatch.setattr(tick, "_run", fake_run)
    monkeypatch.setattr(
        tick,
        "compose_issue_to_pr",
        lambda **kw: intake.append(kw)
        or {"ok": True, "pr": 2, "branch": "ai/fix/2-next"},
    )

    result = tick.compose_tick(config_path=config, live=True)

    assert [item["repo"] for item in intake] == ["a/one"]
    assert result["health"] == "progress"
    assert result["remaining"]["manual_open_ai_prs"] == 1
    assert not any(
        action.get("step") == "skip_ready_open_ai_pr"
        for action in result["actions"]
    )


def test_malformed_labels_fail_closed(tmp_path, monkeypatch):
    config = _config(tmp_path)

    def fake_run(fn, argv):
        repo = argv[argv.index("--repo") + 1]
        if fn is tick.p_list_prs.main:
            return {
                "ok": True,
                "prs": [_pr(labels={"name": "ai:needs-review"})]
                if repo == "a/one"
                else [],
            }
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


def test_pr_survey_failure_blocks_only_failed_repo(tmp_path, monkeypatch):
    config = _config(tmp_path, max_triage_per_tick=5)
    triage = []
    intake = []

    def fake_run(fn, argv):
        repo = argv[argv.index("--repo") + 1]
        if fn is tick.p_list_prs.main:
            return (
                {"ok": False, "error": "boom"}
                if repo == "a/one"
                else {"ok": True, "prs": []}
            )
        if fn is tick.p_list_inbox.main:
            return {"ok": True, "issues": [{"number": 3, "repo": repo}]}
        if fn is tick.p_list_issues.main:
            return {
                "ok": True,
                "issues": [{"number": 2, "repo": repo, "title": "next"}],
            }
        if fn is tick.p_intake.main:
            return _intake_ok()
        raise AssertionError(fn)

    monkeypatch.setattr(tick, "run_preflight", lambda *a, **kw: {"ok": True})
    monkeypatch.setattr(tick, "_run", fake_run)
    monkeypatch.setattr(
        tick,
        "run_path",
        lambda **kw: triage.append(kw)
        or {"ok": True, "applied": True, "decision": {"decision": "ready"}},
    )
    monkeypatch.setattr(
        tick,
        "compose_issue_to_pr",
        lambda **kw: intake.append(kw) or {"ok": True, "pr": 2, "branch": "ai/fix/2-next"},
    )
    result = tick.compose_tick(config_path=config, live=True)

    assert result["remaining"]["survey_errors"] == 1
    assert result["remaining"]["intake_skip_reason"] is None
    assert any(
        a.get("step") == "skip_inbox_triage_survey_failed" and a.get("repo") == "a/one"
        for a in result["actions"]
    )
    assert any(
        a.get("step") == "skip_issue_to_pr_survey_failed" and a.get("repo") == "a/one"
        for a in result["actions"]
    )
    # Clean repo two may still triage + implement.
    assert any(t.get("repo") == "a/two" for t in triage)
    assert len(intake) == 1
    assert intake[0]["repo"] == "a/two"


def test_needs_human_discovered_this_pass_becomes_manual(tmp_path, monkeypatch):
    config = _config(tmp_path)

    def fake_run(fn, argv):
        repo = argv[argv.index("--repo") + 1]
        if fn is tick.p_list_prs.main:
            return {"ok": True, "prs": [_pr(labels=[])] if repo == "a/one" else []}
        if fn is tick.p_list_inbox.main:
            return {"ok": True, "issues": []}
        if fn is tick.p_list_issues.main:
            return {
                "ok": True,
                "issues": [{"number": 2, "repo": repo, "title": "next"}]
                if repo == "a/two"
                else [],
            }
        if fn is tick.p_checks.main:
            return {"ok": True, "status": "none", "merge_ok": True}
        if fn is tick.p_intake.main:
            return _intake_ok()
        raise AssertionError(fn)

    intake = []
    monkeypatch.setattr(tick, "run_preflight", lambda *a, **kw: {"ok": True})
    monkeypatch.setattr(tick, "_run", fake_run)
    monkeypatch.setattr(
        tick,
        "compose_pr_triage",
        lambda **_: {
            "ok": True,
            "skipped": True,
            "repairable": False,
            "review": {"verdict": "needs_human", "secrets": False},
        },
    )
    monkeypatch.setattr(
        tick,
        "compose_issue_to_pr",
        lambda **kw: intake.append(kw) or {"ok": True, "pr": 2, "branch": "ai/fix/2-next"},
    )
    result = tick.compose_tick(config_path=config, live=True)
    assert len(intake) == 1
    assert intake[0]["repo"] == "a/two"
    assert result["remaining"]["manual_open_ai_prs"] == 1


def test_configured_k_budget_honors_breadth_across_clean_repos(tmp_path, monkeypatch):
    """K>1 is a rare pass breadth budget across clean repos — not concurrency."""
    repos = ("a/one", "a/two", "a/three", "a/four")
    config = _config(tmp_path, repos=repos, max_issue_to_pr_per_pass=3)

    def fake_run(fn, argv):
        repo = argv[argv.index("--repo") + 1]
        if fn is tick.p_list_prs.main:
            return {"ok": True, "prs": []}
        if fn is tick.p_list_inbox.main:
            return {"ok": True, "issues": []}
        if fn is tick.p_list_issues.main:
            return {
                "ok": True,
                "issues": [{"number": 2, "repo": repo, "title": f"work-{repo}"}],
            }
        if fn is tick.p_intake.main:
            return _intake_ok()
        raise AssertionError(fn)

    intake = []
    monkeypatch.setattr(tick, "run_preflight", lambda *a, **kw: {"ok": True})
    monkeypatch.setattr(tick, "_run", fake_run)
    monkeypatch.setattr(
        tick,
        "compose_issue_to_pr",
        lambda **kw: intake.append(kw)
        or {
            "ok": True,
            "pr": 10 + len(intake),
            "branch": f"ai/fix/2-{kw['repo'].replace('/', '-')}",
        },
    )
    result = tick.compose_tick(config_path=config, live=True)

    assert len(intake) == 3
    # Default priority ties → alphabetical among managed names.
    assert [x["repo"] for x in intake] == ["a/four", "a/one", "a/three"]
    assert result["remaining"]["issue_to_pr_started"] == 3
    assert result["remaining"]["max_issue_to_pr_per_pass"] == 3
    assert result["remaining"]["open_ai_prs"] == 3
    by_repo = {row["repo"]: row for row in result["remaining"]["by_repo"]}
    assert by_repo["a/one"]["actionable_open_ai_prs"] == 1
    assert by_repo["a/two"]["ready"] == 1  # K exhausted; still ready
    assert result.get("pass_receipt_path")


def test_stuck_repo_does_not_block_ready_repo_under_k(tmp_path, monkeypatch):
    config = _config(
        tmp_path,
        repos=("a/stuck", "a/ready"),
        max_issue_to_pr_per_pass=3,
    )

    def fake_run(fn, argv):
        repo = argv[argv.index("--repo") + 1]
        if fn is tick.p_list_prs.main:
            # Stuck repo already has an open AI PR (pending checks).
            return {
                "ok": True,
                "prs": [_pr(number=9)] if repo == "a/stuck" else [],
            }
        if fn is tick.p_list_inbox.main:
            return {"ok": True, "issues": []}
        if fn is tick.p_list_issues.main:
            return {
                "ok": True,
                "issues": [{"number": 2, "repo": repo, "title": "next"}],
            }
        if fn is tick.p_checks.main:
            return {"ok": True, "status": "pending"}
        if fn is tick.p_intake.main:
            return _intake_ok()
        raise AssertionError(fn)

    intake = []
    monkeypatch.setattr(tick, "run_preflight", lambda *a, **kw: {"ok": True})
    monkeypatch.setattr(tick, "_run", fake_run)
    monkeypatch.setattr(
        tick,
        "compose_issue_to_pr",
        lambda **kw: intake.append(kw) or {"ok": True, "pr": 2, "branch": "ai/fix/2-next"},
    )
    result = tick.compose_tick(config_path=config, live=True)

    assert len(intake) == 1
    assert intake[0]["repo"] == "a/ready"
    assert result["remaining"]["issue_to_pr_started"] == 1


def test_never_second_ai_pr_in_same_repo(tmp_path, monkeypatch):
    config = _config(
        tmp_path,
        repos=("a/one",),
        max_issue_to_pr_per_pass=3,
    )

    def fake_run(fn, argv):
        if fn is tick.p_list_prs.main:
            return {"ok": True, "prs": []}
        if fn is tick.p_list_inbox.main:
            return {"ok": True, "issues": []}
        if fn is tick.p_list_issues.main:
            return {
                "ok": True,
                "issues": [
                    {"number": 2, "repo": "a/one", "title": "first"},
                    {"number": 3, "repo": "a/one", "title": "second"},
                ],
            }
        if fn is tick.p_intake.main:
            return _intake_ok()
        raise AssertionError(fn)

    intake = []
    monkeypatch.setattr(tick, "run_preflight", lambda *a, **kw: {"ok": True})
    monkeypatch.setattr(tick, "_run", fake_run)
    monkeypatch.setattr(
        tick,
        "compose_issue_to_pr",
        lambda **kw: intake.append(kw)
        or {"ok": True, "pr": kw["issue_number"], "branch": f"ai/fix/{kw['issue_number']}-x"},
    )
    result = tick.compose_tick(config_path=config, live=True)

    assert len(intake) == 1
    assert result["remaining"]["issue_to_pr_started"] == 1
    assert result["remaining"]["open_ai_prs"] == 1


def test_needs_feedback_issue_does_not_block_other_repo_intake(tmp_path, monkeypatch):
    """ai:needs-feedback is a residual mailbox — mill continues other repos."""
    config = _config(tmp_path)

    def fake_run(fn, argv):
        repo = argv[argv.index("--repo") + 1]
        if fn is tick.p_list_prs.main:
            return {"ok": True, "prs": []}
        if fn is tick.p_list_inbox.main:
            # Parked feedback issues are not inbox; empty undecided is fine.
            return {"ok": True, "issues": []}
        if fn is tick.p_list_issues.main:
            if repo == "a/one":
                # Ready survey never returns needs-feedback; simulate empty ready there.
                return {"ok": True, "issues": []}
            return {"ok": True, "issues": [{"number": 2, "repo": repo, "title": "next"}]}
        if fn is tick.p_intake.main:
            return _intake_ok()
        raise AssertionError(fn)

    intake = []
    monkeypatch.setattr(tick, "run_preflight", lambda *a, **kw: {"ok": True})
    monkeypatch.setattr(tick, "_run", fake_run)
    monkeypatch.setattr(
        tick,
        "compose_issue_to_pr",
        lambda **kw: intake.append(kw) or {"ok": True, "pr": 2, "branch": "ai/fix/2-next"},
    )
    result = tick.compose_tick(config_path=config, live=True)
    assert len(intake) == 1
    assert intake[0]["repo"] == "a/two"
    assert result["remaining"]["intake_skip_reason"] is None


def test_only_parked_needs_review_is_waiting_not_stall(tmp_path, monkeypatch):
    """No ready work + parked mailbox PR → waiting, never stall/recovery bait."""
    config = _config(tmp_path, repos=("a/one",))

    def fake_run(fn, argv):
        if fn is tick.p_list_prs.main:
            return {"ok": True, "prs": [_pr(labels=["ai:needs-review"])]}
        if fn in {tick.p_list_inbox.main, tick.p_list_issues.main}:
            return {"ok": True, "issues": []}
        raise AssertionError(fn)

    monkeypatch.setattr(tick, "run_preflight", lambda *a, **kw: {"ok": True})
    monkeypatch.setattr(tick, "_run", fake_run)
    monkeypatch.setattr(
        tick,
        "compose_issue_to_pr",
        lambda **_: (_ for _ in ()).throw(AssertionError("intake ran")),
    )
    result = tick.compose_tick(config_path=config, live=True)
    assert result["health"] == "waiting"
    assert result["ok"] is True
    assert result["idle"] is False
    assert result["remaining"]["manual_open_ai_prs"] == 1
    assert result["remaining"]["actionable_open_ai_prs"] == 0
    assert result["remaining"]["ready"] == 0
