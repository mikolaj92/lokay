from pathlib import Path

from lokay.proc import dispatch_implement as d
from lokay.proc import detach_issue_to_pr as detach_mod


def test_detach_writes_start_and_pid_to_log(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))

    class FakePopen:
        def __init__(self, _argv, **_kwargs):
            self.pid = 4242

    out = detach_mod.detach_issue_to_pr(
        repo=detach_mod.MINI_MILL_REPO, issue=9, config_path=None, popen=FakePopen
    )

    assert out["ok"] is True
    assert Path(out["log"]).read_text(encoding="ascii") == (
        "started issue=9 pid-pending\npid=4242\n"
    )


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
        "repos": ["mikolaj92/lokay", "mikolaj92/Fala"],
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
    assert out.get("started") == 1
    assert len(seen) == 1
    assert all(flag is True for _, flag in seen)
    argv0, _ = seen[0]
    # FakePopen only stored argv + start_new_session; log path is on the action.
    working = __import__("json").loads((tmp_path / "working.json").read_text())
    launched = [a for a in working["actions"] if a.get("step") == "issue_to_pr"]
    assert len(launched) == 1
    assert [a for a in working["actions"] if a.get("step") == "skip_repo_outside_mini_mill"] == [
        {
            "step": "skip_repo_outside_mini_mill",
            "repo": "mikolaj92/Fala",
            "skipped": True,
            "reason": "repo_not_delivered_by_mini_mill",
        }
    ]
    for row in launched:
        log = row.get("log") or ""
        assert "issue-to-pr-" in log
        assert log.endswith(".log")


def test_blocked_plan_only_is_parked_once(monkeypatch, tmp_path):
    """A terminal plan-only failure must leave the ready survey lane."""
    from lokay.passkit import io as pass_io

    begin = {
        "live": True,
        "issue_budget": 1,
        "stuck_path": str(tmp_path / "stuck.json"),
        "max_fail": 1,
        "blocked_label": "ai:blocked",
        "repos": ["mikolaj92/lokay"],
    }
    working = {
        "actions": [],
        "progress": 0,
        "stuck": {},
        "ready_by_repo": {
            "mikolaj92/lokay": [{"repo": "mikolaj92/lokay", "number": 11}]
        },
    }
    (tmp_path / "begin.json").write_text(__import__("json").dumps(begin))
    (tmp_path / "working.json").write_text(__import__("json").dumps(working))
    (tmp_path / "implement.json").write_text(
        __import__("json").dumps({"clean_repos": ["mikolaj92/lokay"], "issue_budget": 1})
    )
    monkeypatch.setattr(pass_io, "begin_path", lambda _p: tmp_path / "begin.json")
    monkeypatch.setattr(pass_io, "working_path", lambda _p: tmp_path / "working.json")
    monkeypatch.setattr(pass_io, "implement_path", lambda _p: tmp_path / "implement.json")
    monkeypatch.setattr(d, "_live_ps_text", lambda: "")
    monkeypatch.setattr(d, "inspect_mutex", lambda **_k: {"busy": False, "pids": []})
    monkeypatch.setattr(
        d,
        "run_select",
        lambda _main, payload: {"ok": True, "selected": payload["issues"][0]},
    )
    calls = []

    def fake_proc(main, argv):
        calls.append((main, argv))
        if main is d.p_intake.main:
            return {"ok": True, "implementable": True, "applied": False}
        return {"ok": True, "applied": True}

    monkeypatch.setattr(d, "run_proc", fake_proc)
    monkeypatch.setattr(
        d,
        "detach_issue_to_pr",
        lambda **_kwargs: {
            "ok": False,
            "reason": "plan_only",
            "error": "plan_only",
        },
    )
    monkeypatch.setattr(d, "save_stuck", lambda *_a, **_k: None)
    monkeypatch.setattr(d, "write_pass_receipt", lambda *_a, **_k: None)
    monkeypatch.setattr(d, "build_pass_receipt", lambda **_k: {})

    out = d.run_dispatch_implement(pass_dir=str(tmp_path), config_path=None, live=True)

    assert out.get("ok") is True
    park_calls = [(main, argv) for main, argv in calls if main is d.p_park.main]
    assert park_calls == [
        (d.p_park.main, ["--live", "--repo", "mikolaj92/lokay", "--issue", "11"])
    ]
    from lokay.proc import close_issue

    assert [(main, argv) for main, argv in calls if main is close_issue.main] == []


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


def test_dispatch_continues_when_receipt_state_is_unknown(monkeypatch, tmp_path):
    """Stale/unreadable receipts are idle — dispatch still detaches K=1."""
    from lokay.passkit import io as pass_io

    begin = {
        "live": True,
        "issue_budget": 1,
        "stuck_path": str(tmp_path / "stuck.json"),
        "repos": ["mikolaj92/lokay"],
    }
    working = {"actions": [], "progress": 0, "stuck": {}, "ready_by_repo": {"mikolaj92/lokay": [{"repo": "mikolaj92/lokay", "number": 1}]}}
    (tmp_path / "begin.json").write_text(__import__("json").dumps(begin))
    (tmp_path / "working.json").write_text(__import__("json").dumps(working))
    (tmp_path / "implement.json").write_text(__import__("json").dumps({"clean_repos": ["mikolaj92/lokay"], "issue_budget": 1}))
    monkeypatch.setattr(pass_io, "begin_path", lambda _p: tmp_path / "begin.json")
    monkeypatch.setattr(pass_io, "working_path", lambda _p: tmp_path / "working.json")
    monkeypatch.setattr(pass_io, "implement_path", lambda _p: tmp_path / "implement.json")
    monkeypatch.setattr(d, "has_unreadable_issue_to_pr_receipts", lambda: True)
    monkeypatch.setattr(d, "_live_ps_text", lambda: "")
    monkeypatch.setattr(d, "inspect_mutex", lambda **_k: {"busy": False, "pids": []})
    monkeypatch.setattr(
        d,
        "run_select",
        lambda _main, payload: {"ok": True, "selected": payload["issues"][0]},
    )
    monkeypatch.setattr(
        d,
        "run_proc",
        lambda _main, _argv: {"ok": True, "implementable": True, "applied": False},
    )
    monkeypatch.setattr(
        d,
        "detach_issue_to_pr",
        lambda **kwargs: {"ok": True, "detached": True, "repo": kwargs["repo"], "issue": kwargs["issue"], "pid": 4242},
    )
    monkeypatch.setattr(d, "save_stuck", lambda *_a, **_k: None)
    monkeypatch.setattr(d, "write_pass_receipt", lambda *_a, **_k: None)
    monkeypatch.setattr(d, "build_pass_receipt", lambda **_k: {})

    out = d.run_dispatch_implement(pass_dir=str(tmp_path), config_path=None, live=True)

    assert out.get("ok") is True
    assert out.get("reason") != "receipt_state_unknown"
    working_out = __import__("json").loads((tmp_path / "working.json").read_text())
    assert any(a.get("step") == "receipts_unreadable" for a in working_out.get("actions") or [])
    assert any(a.get("step") == "issue_to_pr" for a in working_out.get("actions") or [])


def test_malformed_no_pid_receipts_are_unknown(tmp_path):
    import json

    for index, payload in enumerate(
        [
            {},
            {"detached": True, "repo": "owner/repo", "issue": 9},
            {"repo": "owner/repo", "issue": 9},
            {"repo": "owner/repo", "issue": 9, "started_ts": "not-a-time"},
        ]
    ):
        path = tmp_path / f"malformed-{index}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")

    assert detach_mod.has_unreadable_issue_to_pr_receipts(tmp_path) is True
    assert detach_mod.live_issue_to_pr_receipts(tmp_path, pid_alive=lambda _pid: False) == []


def test_complete_cycle_start_metric_is_readable_but_filename_is_distinct(tmp_path):
    import json

    metric = {
        "repo": "owner/repo",
        "issue": 9,
        "started_ts": "2026-08-18T12:34:56Z",
    }
    valid = tmp_path / "owner__repo__9.json"
    valid.write_text(json.dumps(metric), encoding="utf-8")

    assert detach_mod.has_unreadable_issue_to_pr_receipts(tmp_path) is False
    assert detach_mod.live_issue_to_pr_receipts(tmp_path, pid_alive=lambda _pid: False) == []

    valid.rename(tmp_path / "owner__repo-9.json")
    assert detach_mod.has_unreadable_issue_to_pr_receipts(tmp_path) is True



def test_cycle_start_metric_requires_exact_utc_timestamp(tmp_path):
    import json

    for index, started_ts in enumerate(
        [
            "2026-1-1T1:2:3Z",
            "2026-01-01T00:00:00z",
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00.000Z",
        ]
    ):
        path = tmp_path / "owner__repo__9.json"
        path.write_text(
            json.dumps(
                {"repo": "owner/repo", "issue": 9, "started_ts": started_ts}
            ),
            encoding="utf-8",
        )
        assert detach_mod.has_unreadable_issue_to_pr_receipts(tmp_path) is True, index
        path.unlink()

def test_cycle_start_metric_rejects_boolean_issue(tmp_path):
    import json

    path = tmp_path / "owner__repo__1.json"
    path.write_text(
        json.dumps(
            {
                "repo": "owner/repo",
                "issue": True,
                "started_ts": "2026-08-18T12:34:56Z",
            }
        ),
        encoding="utf-8",
    )

    assert detach_mod.has_unreadable_issue_to_pr_receipts(tmp_path) is True


def test_dead_or_zero_pid_receipt_is_readable_idle(tmp_path):
    import json

    path = tmp_path / "owner__repo-9.json"
    path.write_text(
        json.dumps(
            {
                "ok": False,
                "reason": "token_missing",
                "repo": "owner/repo",
                "issue": 9,
                "pid": 0,
            }
        ),
        encoding="utf-8",
    )
    assert detach_mod.has_unreadable_issue_to_pr_receipts(tmp_path) is False
    assert detach_mod.live_issue_to_pr_receipts(tmp_path, pid_alive=lambda _pid: False) == []


def test_failed_plan_only_receipt_without_pid_is_readable_idle(tmp_path):
    import json

    path = tmp_path / "owner__repo-9.json"
    path.write_text(
        json.dumps(
            {
                "ok": False,
                "reason": "plan_only",
                "repo": "owner/repo",
                "issue": 9,
                "reaped": True,
            }
        ),
        encoding="utf-8",
    )
    assert detach_mod.has_unreadable_issue_to_pr_receipts(tmp_path) is False
    assert detach_mod.live_issue_to_pr_receipts(tmp_path, pid_alive=lambda _pid: False) == []

