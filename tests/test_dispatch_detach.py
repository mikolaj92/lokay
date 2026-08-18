from lokay.proc import dispatch_implement as d
from lokay.proc import detach_issue_to_pr as detach_mod


def test_detach_does_not_wait(monkeypatch, tmp_path):
    seen = []

    class FakePopen:
        def __init__(self, argv, **kwargs):
            seen.append((argv, kwargs.get("start_new_session")))
            self.pid = 4242

    monkeypatch.setattr(d, "detach_issue_to_pr", lambda **k: detach_mod.detach_issue_to_pr(**k, popen=FakePopen))
    begin = {
        "live": True,
        "issue_budget": 4,
        "max_issue_to_pr_per_pass": 4,
        "stuck_path": str(tmp_path / "stuck.json"),
        "state_path": str(tmp_path / "state.jsonl"),
        "max_fail": 2,
        "blocked_label": "ai:blocked",
        "merge_enabled": True,
    }
    working = {
        "actions": [],
        "progress": 0,
        "stuck": {},
        "remaining_ready": 2,
        "remaining_prs": 0,
        "actionable_prs": 0,
        "blocked_this_pass": 0,
        "issue_to_pr_started": 0,
        "prs_by_repo": {},
        "ready_by_repo": {
            "mikolaj92/lokay": [{"repo": "mikolaj92/lokay", "number": 1, "title": "a"}],
            "mikolaj92/Fala": [{"repo": "mikolaj92/Fala", "number": 2, "title": "b"}],
        },
    }
    (tmp_path / "begin.json").write_text(__import__("json").dumps(begin))
    # passkit io uses fixed names — go through run with patched io
    from lokay.passkit import io as pass_io

    monkeypatch.setattr(pass_io, "begin_path", lambda p: tmp_path / "begin.json")
    monkeypatch.setattr(pass_io, "working_path", lambda p: tmp_path / "working.json")
    monkeypatch.setattr(pass_io, "implement_path", lambda p: tmp_path / "implement.json")
    (tmp_path / "working.json").write_text(__import__("json").dumps(working))
    (tmp_path / "implement.json").write_text(
        __import__("json").dumps({"clean_repos": ["mikolaj92/lokay", "mikolaj92/Fala"], "issue_budget": 4})
    )

    def fake_select(main, payload):
        issues = payload["issues"]
        return {"ok": True, "selected": issues[0]}

    def fake_proc(main, argv):
        return {"ok": True, "implementable": True, "applied": False}

    monkeypatch.setattr(d, "run_select", fake_select)
    monkeypatch.setattr(d, "run_proc", fake_proc)
    monkeypatch.setattr(d, "save_stuck", lambda *a, **k: None)
    monkeypatch.setattr(d, "_live_ps_text", lambda: "")
    monkeypatch.setattr(d, "inspect_mutex", lambda **k: {"ok": True, "busy": False})
    monkeypatch.setenv("HOME", str(tmp_path))
    out = d.run_dispatch_implement(pass_dir=str(tmp_path), config_path=None, live=True)
    assert out.get("ok") is True
    assert out.get("detached") is True
    assert out.get("started") == 2
    assert len(seen) == 2
    assert all(flag is True for _, flag in seen)
    argv0, _ = seen[0]
    # FakePopen only stored argv + start_new_session; log path is on the action.
    working = __import__("json").loads((tmp_path / "working.json").read_text())
    launched = [a for a in working["actions"] if a.get("step") == "issue_to_pr"]
    assert len(launched) == 2
    for row in launched:
        log = row.get("log") or ""
        assert "issue-to-pr-" in log
        assert log.endswith(".log")


def test_dispatch_refuses_to_launch_when_repo_mutex_is_unknown(monkeypatch, tmp_path):
    """A failed live ps probe is unknown, never an all-idle mutex snapshot."""
    from lokay.passkit import io as pass_io

    begin = {
        "live": True,
        "issue_budget": 1,
        "stuck_path": str(tmp_path / "stuck.json"),
    }
    working = {
        "actions": [],
        "progress": 0,
        "stuck": {},
        "ready_by_repo": {"owner/repo": [{"repo": "owner/repo", "number": 1}]},
    }
    (tmp_path / "begin.json").write_text(__import__("json").dumps(begin))
    (tmp_path / "working.json").write_text(__import__("json").dumps(working))
    (tmp_path / "implement.json").write_text(
        __import__("json").dumps({"clean_repos": ["owner/repo"], "issue_budget": 1})
    )
    monkeypatch.setattr(pass_io, "begin_path", lambda _p: tmp_path / "begin.json")
    monkeypatch.setattr(pass_io, "working_path", lambda _p: tmp_path / "working.json")
    monkeypatch.setattr(pass_io, "implement_path", lambda _p: tmp_path / "implement.json")
    monkeypatch.setattr(d, "_live_ps_text", lambda: (_ for _ in ()).throw(RuntimeError("ps unavailable")))
    monkeypatch.setattr(
        d,
        "detach_issue_to_pr",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("must not detach when mutex is unknown")),
    )

    out = d.run_dispatch_implement(pass_dir=str(tmp_path), config_path=None, live=True)

    assert out == {
        "ok": False,
        "error": "cannot inspect repo mutex; refusing issue_to_pr dispatch",
        "pass_dir": str(tmp_path),
        "reason": "repo_mutex_unknown",
        "error_detail": "ps unavailable",
    }


def test_dispatch_refuses_to_launch_when_receipt_state_is_unknown(monkeypatch, tmp_path):
    """Direct dispatch has the same fail-closed lifecycle boundary as reap."""
    from lokay.passkit import io as pass_io

    begin = {"live": True, "issue_budget": 1, "stuck_path": str(tmp_path / "stuck.json")}
    working = {"actions": [], "progress": 0, "stuck": {}, "ready_by_repo": {"owner/repo": [{"repo": "owner/repo", "number": 1}]}}
    (tmp_path / "begin.json").write_text(__import__("json").dumps(begin))
    (tmp_path / "working.json").write_text(__import__("json").dumps(working))
    (tmp_path / "implement.json").write_text(__import__("json").dumps({"clean_repos": ["owner/repo"], "issue_budget": 1}))
    monkeypatch.setattr(pass_io, "begin_path", lambda _p: tmp_path / "begin.json")
    monkeypatch.setattr(pass_io, "working_path", lambda _p: tmp_path / "working.json")
    monkeypatch.setattr(pass_io, "implement_path", lambda _p: tmp_path / "implement.json")
    monkeypatch.setattr(d, "has_unreadable_issue_to_pr_receipts", lambda: True)
    monkeypatch.setattr(
        d,
        "detach_issue_to_pr",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("must not detach when receipts are unknown")),
    )

    out = d.run_dispatch_implement(pass_dir=str(tmp_path), config_path=None, live=True)

    assert out == {
        "ok": False,
        "error": "cannot inspect issue_to_pr receipts; refusing dispatch",
        "pass_dir": str(tmp_path),
        "reason": "receipt_state_unknown",
    }
