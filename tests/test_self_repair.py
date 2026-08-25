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
