from types import SimpleNamespace

from lokay import self_repair


def cfg(tmp_path, **kw):
    base = dict(
        state_path=tmp_path / "state.jsonl",
        executor_enabled=True,
        incident_repo="mikolaj92/lokay",
    )
    base.update(kw)
    return SimpleNamespace(**base)


def unhealthy(url="https://github.com/mikolaj92/lokay/issues/44"):
    return {
        "ok": False,
        "carrier_ok": True,
        "integrity_ok": False,
        "fingerprint": "abc",
        "incident_url": url,
        "findings": [{"name": "fala_smoke", "ok": False}],
    }


def setup_lane(monkeypatch, tmp_path, **cfg_kw):
    monkeypatch.setattr(self_repair, "load_config", lambda p: cfg(tmp_path, **cfg_kw))
    monkeypatch.setattr(
        self_repair, "trusted_fala_manifest", lambda: tmp_path / "trusted.toml"
    )


def test_self_repair_resume_candidate_skips_agent_and_commit_but_revalidates(
    tmp_path, monkeypatch
):
    from lokay.organ.self_repair import handle_self_repair
    from lokay.proc import self_repair_push_main as push_module

    calls: list[tuple[object, list[str]]] = []

    def fake_atom(main, argv):
        calls.append((main, list(argv)))
        return {"ok": True, "validated": True, "commit": "c" * 40}

    from lokay import fala_organ

    monkeypatch.setattr(fala_organ, "_run_atom_main", fake_atom)
    prepared = {
        "ok": True,
        "worktree": str(tmp_path),
        "base_sha": "a" * 40,
        "resumed": True,
        "candidate_commit": "c" * 40,
    }
    ctx = {
        "cfg": [],
        "live": [],
        "repo": "mikolaj92/lokay",
        "issue_number": 1,
        "pr_number": None,
        "repair_mode": False,
        "branch": "",
        "run_atom_main": fake_atom,
    }

    agent = handle_self_repair(
        "self_repair_run_agent", {}, {"self_repair_prepare": prepared}, ctx
    )
    committed = handle_self_repair(
        "self_repair_commit", {}, {"self_repair_prepare": prepared}, ctx
    )
    monkeypatch.setattr(
        "lokay.proc.self_repair_validate_subflow.run",
        lambda **kwargs: {
            "ok": True,
            "validated": True,
            "commit": kwargs["expected_commit"],
        },
    )
    validated = handle_self_repair(
        "self_repair_validate",
        {"fingerprint": "deadbeef"},
        {
            "self_repair_prepare": prepared,
            "self_repair_commit": committed,
        },
        ctx,
    )
    handle_self_repair(
        "self_repair_push_main",
        {},
        {
            "self_repair_prepare": prepared,
            "self_repair_validate": validated,
            "self_repair_commit": committed,
        },
        ctx,
    )

    assert agent["reason"] == "resume_existing_candidate"
    assert committed["reason"] == "resume_committed_candidate"
    assert calls == [
        (
            push_module.main,
            [
                "--worktree",
                str(tmp_path),
                "--base-sha",
                "a" * 40,
                "--validated",
                "--expected-commit",
                "c" * 40,
            ],
        ),
    ]
    assert validated["validated"] is True


def test_self_repair_dirty_resume_skips_agent_but_runs_validation_and_commit(
    tmp_path, monkeypatch
):
    from lokay.organ.self_repair import handle_self_repair
    from lokay.proc import commit_all

    calls: list[tuple[object, list[str]]] = []

    def fake_atom(main, argv):
        calls.append((main, list(argv)))
        return {
            "ok": True,
            "validated": True,
            "committed": True,
            "commit": "d" * 40,
        }

    from lokay import fala_organ

    monkeypatch.setattr(fala_organ, "_run_atom_main", fake_atom)
    prepared = {
        "ok": True,
        "worktree": str(tmp_path),
        "base_sha": "a" * 40,
        "resumed": True,
        "candidate_commit": "",
    }
    ctx = {
        "cfg": [],
        "live": [],
        "repo": "mikolaj92/lokay",
        "issue_number": 1,
        "pr_number": None,
        "repair_mode": False,
        "branch": "",
        "run_atom_main": fake_atom,
    }

    agent = handle_self_repair(
        "self_repair_run_agent", {}, {"self_repair_prepare": prepared}, ctx
    )
    committed = handle_self_repair(
        "self_repair_commit",
        {"fingerprint": "deadbeef"},
        {"self_repair_prepare": prepared},
        ctx,
    )
    monkeypatch.setattr(
        "lokay.proc.self_repair_validate_subflow.run",
        lambda **kwargs: {
            "ok": True,
            "validated": True,
            "commit": kwargs["expected_commit"],
        },
    )
    handle_self_repair(
        "self_repair_validate",
        {"fingerprint": "deadbeef"},
        {
            "self_repair_prepare": prepared,
            "self_repair_commit": committed,
        },
        ctx,
    )

    assert agent["reason"] == "resume_existing_candidate"
    assert calls == [
        (
            commit_all.main,
            [
                "--worktree",
                str(tmp_path),
                "--message",
                "self-repair: deadbeef",
            ],
        ),
    ]


def test_commit_all_reports_exact_created_commit(tmp_path, monkeypatch, capsys):
    from lokay.proc import commit_all as commit_module

    worktree = tmp_path / "wt"
    worktree.mkdir()

    class FakeRun:
        def run_checked(self, spec, *, live):
            assert spec.argv[1:3] == ("rev-parse", "HEAD")
            return SimpleNamespace(stdout="c" * 40 + "\n", returncode=0)

    monkeypatch.setattr(commit_module, "load_cfg", lambda _args: SimpleNamespace())
    monkeypatch.setattr(commit_module, "mutations_allowed", lambda **_kwargs: True)
    monkeypatch.setattr(commit_module, "runner", FakeRun)
    monkeypatch.setattr(commit_module, "commit_all", lambda *_args, **_kwargs: True)

    code = commit_module.main(
        ["--live", "--worktree", str(worktree), "--message", "fix"]
    )
    payload = __import__("json").loads(capsys.readouterr().out.strip())

    assert code == 0
    assert payload["committed"] is True
    assert payload["commit"] == "c" * 40


def test_self_repair_facade_invokes_one_authored_entry(monkeypatch):
    calls = []
    preflight = unhealthy()
    monkeypatch.setattr(
        "lokay.proc.self_repair_entry_subflow.run",
        lambda **k: calls.append(k) or {"ok": True, "health": "restart_required"},
    )
    result = self_repair.run_self_repair("x", preflight)
    assert result["health"] == "restart_required"
    assert calls == [{"config_path": "x", "preflight": preflight}]


def test_self_repair_facade_contains_no_routing():
    import inspect

    source = inspect.getsource(self_repair.run_self_repair)
    assert "if " not in source and "run_path" not in source

def test_self_repair_validate_fail_soft_skips_push_and_summarizes_failed(
    tmp_path, monkeypatch
):
    """Validate not-validated still ok=True; push/activate/preflight/close soft-skip."""
    from lokay.organ.self_repair import handle_self_repair
    from lokay.proc import self_repair_push_main as push_module
    from lokay.proc.summarize_self_repair import summarize

    calls: list[tuple[object, list[str]]] = []

    def fake_atom(main, argv):
        calls.append((main, list(argv)))
        raise AssertionError(f"atom should not run on fail-closed: {main}")

    prepared = {
        "ok": True,
        "worktree": str(tmp_path),
        "base_sha": "a" * 40,
    }
    committed = {"ok": True, "commit": "c" * 40}
    ctx = {
        "cfg": [],
        "live": [],
        "repo": "mikolaj92/lokay",
        "issue_number": 44,
        "pr_number": None,
        "repair_mode": False,
        "branch": "",
        "run_atom_main": fake_atom,
    }
    reclaim_calls: list[dict] = []
    monkeypatch.setattr(
        "lokay.fala_journal.reclaim_self_repair_incomplete_journals",
        lambda **kwargs: reclaim_calls.append(kwargs) or {"ok": True, "reclaimed": []},
    )
    monkeypatch.setattr(
        "lokay.proc.self_repair_validate_subflow.run",
        lambda **kwargs: {
            "ok": False,
            "validated": False,
            "error": "suite_failed",
            "commit": kwargs["expected_commit"],
        },
    )
    validated = handle_self_repair(
        "self_repair_validate",
        {"fingerprint": "deadbeef"},
        {"self_repair_prepare": prepared, "self_repair_commit": committed},
        ctx,
    )
    assert validated["ok"] is True
    assert validated["validated"] is False
    assert validated["route"] == "fail_closed"
    assert reclaim_calls == [{}]

    pushed = handle_self_repair(
        "self_repair_push_main",
        {},
        {
            "self_repair_prepare": prepared,
            "self_repair_validate": validated,
            "self_repair_commit": committed,
        },
        ctx,
    )
    assert pushed["ok"] is True
    assert pushed["skipped"] is True
    assert pushed["route"] == "fail_closed"
    assert pushed["pushed"] is False

    activated = handle_self_repair(
        "self_repair_activate",
        {"config_path": str(tmp_path / "config.yaml"), "live": False},
        {"self_repair_prepare": prepared, "self_repair_push_main": pushed},
        ctx,
    )
    assert activated["ok"] is True
    assert activated["skipped"] is True
    assert activated["route"] == "fail_closed"

    preflight = handle_self_repair(
        "self_repair_preflight",
        {"config_path": str(tmp_path / "config.yaml")},
        {"self_repair_activate": activated},
        ctx,
    )
    assert preflight["ok"] is True
    assert preflight["skipped"] is True
    assert preflight.get("validated") is False

    closed = handle_self_repair(
        "self_repair_close",
        {},
        {"self_repair_preflight": preflight},
        ctx,
    )
    assert closed["ok"] is True
    assert closed["skipped"] is True
    assert closed["closed"] is False

    terminal = summarize(
        preflight=preflight, push=pushed, activate=activated, close=closed
    )
    assert terminal["ok"] is True
    assert terminal["terminal"] == "failed"
    assert terminal["result"]["ok"] is False
    assert calls == []
    # push_module imported only to prove happy-path contrast stays available
    assert push_module.main


def test_self_repair_happy_path_still_pushes(tmp_path, monkeypatch):
    """Validated candidate still invokes push_main atom."""
    from lokay.organ.self_repair import handle_self_repair
    from lokay.proc import self_repair_push_main as push_module

    calls: list[tuple[object, list[str]]] = []

    def fake_atom(main, argv):
        calls.append((main, list(argv)))
        return {"ok": True, "pushed": True, "commit": "c" * 40}

    prepared = {
        "ok": True,
        "worktree": str(tmp_path),
        "base_sha": "a" * 40,
    }
    committed = {"ok": True, "commit": "c" * 40}
    validated = {"ok": True, "validated": True, "commit": "c" * 40}
    ctx = {
        "cfg": [],
        "live": [],
        "repo": "mikolaj92/lokay",
        "issue_number": 1,
        "pr_number": None,
        "repair_mode": False,
        "branch": "",
        "run_atom_main": fake_atom,
    }
    pushed = handle_self_repair(
        "self_repair_push_main",
        {},
        {
            "self_repair_prepare": prepared,
            "self_repair_validate": validated,
            "self_repair_commit": committed,
        },
        ctx,
    )
    assert pushed["pushed"] is True
    assert calls == [
        (
            push_module.main,
            [
                "--worktree",
                str(tmp_path),
                "--base-sha",
                "a" * 40,
                "--validated",
                "--expected-commit",
                "c" * 40,
            ],
        )
    ]
