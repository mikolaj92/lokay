from pathlib import Path
from types import SimpleNamespace

from lokay import self_repair
from lokay.proc import self_repair_validate


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
    monkeypatch.setattr(self_repair, "trusted_fala_manifest", lambda: tmp_path / "trusted.toml")


def test_missing_deduplicated_incident_never_runs_fala(monkeypatch, tmp_path):
    setup_lane(monkeypatch, tmp_path)
    monkeypatch.setattr(self_repair, "run_path", lambda **k: (_ for _ in ()).throw(AssertionError()))
    result = self_repair.run_self_repair("x", unhealthy(url=None))
    assert not result["ok"] and result["reason"] == "deduplicated_incident_unavailable"


def test_bootstrap_dependency_failure_avoids_recursion(monkeypatch, tmp_path):
    setup_lane(monkeypatch, tmp_path)
    value = unhealthy()
    value["findings"] = [{"name": "executor_availability", "ok": False}]
    monkeypatch.setattr(self_repair, "run_path", lambda **k: (_ for _ in ()).throw(AssertionError()))
    result = self_repair.run_self_repair("x", value)
    assert result["reason"] == "bootstrap_dependency_unavailable"


def test_carrier_unhealthy_never_runs_fala(monkeypatch, tmp_path):
    setup_lane(monkeypatch, tmp_path)
    value = unhealthy()
    value["carrier_ok"] = False
    monkeypatch.setattr(self_repair, "run_path", lambda **k: (_ for _ in ()).throw(AssertionError()))
    result = self_repair.run_self_repair("x", value)
    assert result["reason"] == "carrier_unhealthy"


def test_self_repair_is_one_fala_path_and_returns_restart(monkeypatch, tmp_path):
    setup_lane(monkeypatch, tmp_path)
    calls = []

    def fake_path(**kwargs):
        calls.append(kwargs)
        return {
            "ok": True,
            "validated": True,
            "restart_required": True,
            "commit": "deadbeef",
            "incident_closed": True,
            "gate_released": False,
        }

    monkeypatch.setattr(self_repair, "run_path", fake_path)
    result = self_repair.run_self_repair("x", unhealthy())

    assert result["ok"] and result["health"] == "restart_required"
    assert result["commit"] == "deadbeef" and result["gate_released"]
    assert len(calls) == 1
    call = calls[0]
    assert call["path_id"] == "self_repair"
    assert call["repo"] == "mikolaj92/lokay"
    assert call["issue"] == 44 and call["live"] is True
    assert call["extra_inputs"]["fingerprint"] == "abc"


def test_fala_failure_stays_closed(monkeypatch, tmp_path):
    setup_lane(monkeypatch, tmp_path)
    monkeypatch.setattr(self_repair, "run_path", lambda **k: {"ok": False, "error": "push rejected"})
    result = self_repair.run_self_repair("x", unhealthy())
    assert not result["ok"]
    assert result["health"] == "self_repair_failed"
    assert result["reason"] == "fala_self_repair_failed"


def test_self_repair_honors_configured_incident_repo(monkeypatch, tmp_path):
    setup_lane(monkeypatch, tmp_path, incident_repo="acme/ops")
    calls = []

    def fake_path(**kwargs):
        calls.append(kwargs)
        return {"ok": True, "validated": True, "restart_required": True, "commit": "abc"}

    monkeypatch.setattr(self_repair, "run_path", fake_path)
    result = self_repair.run_self_repair(
        "x",
        unhealthy(url="https://github.com/acme/ops/issues/44"),
    )
    assert result["ok"]
    assert calls[0]["repo"] == "acme/ops"
    assert calls[0]["issue"] == 44


def test_self_repair_validate_isolates_pytest_home(tmp_path, monkeypatch):
    worktree = tmp_path / "wt"
    worktree.mkdir()
    seen: dict[str, object] = {}

    class FakeRun:
        def run_checked(self, spec, *, live):
            seen["status"] = spec.argv
            return SimpleNamespace(stdout=" M src/lokay/x.py\n", returncode=0)

        def run(self, spec, *, live):
            if spec.argv and spec.argv[0] == "uv":
                seen["pytest"] = spec
            return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(self_repair_validate, "runner", lambda: FakeRun())
    assert self_repair_validate.main(["--worktree", str(worktree)]) == 0
    spec = seen["pytest"]
    assert spec.argv[:4] == ("uv", "run", "--extra", "dev")
    assert spec.env["HOME"].startswith(str(tmp_path)) or "lokay-self-repair-pytest-" in spec.env["HOME"]
    assert spec.env["HOME"] != str(Path.home())


def test_self_repair_validate_accepts_clean_committed_candidate(
    tmp_path, monkeypatch, capsys
):
    worktree = tmp_path / "wt"
    worktree.mkdir()
    seen: list[tuple[str, ...]] = []

    class FakeRun:
        def run_checked(self, spec, *, live):
            seen.append(spec.argv)
            if spec.argv[1:3] == ("status", "--porcelain"):
                return SimpleNamespace(stdout="", returncode=0)
            if spec.argv[1:3] == ("diff", "--name-only"):
                return SimpleNamespace(stdout="src/lokay/fix.py\n", returncode=0)
            raise AssertionError(spec.argv)

        def run(self, spec, *, live):
            seen.append(spec.argv)
            return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(self_repair_validate, "runner", FakeRun)
    code = self_repair_validate.main(
        ["--worktree", str(worktree), "--base-sha", "a" * 40]
    )

    assert code == 0
    assert any(
        call[1:3] == ("diff", "--name-only") and call[-1] == f"{'a' * 40}...HEAD"
        for call in seen
    )
    assert ("git", "diff", "--check") in seen
    assert ("git", "diff", "--cached", "--check") in seen
    assert ("git", "diff", "--check", f"{'a' * 40}...HEAD") in seen
    assert '"validated": true' in capsys.readouterr().out.lower()


def test_self_repair_resume_candidate_skips_agent_and_commit_but_revalidates(
    tmp_path, monkeypatch
):
    from lokay.organ.self_repair import handle_self_repair
    from lokay.proc import self_repair_push_main as push_module
    from lokay.proc import self_repair_validate as validate_module

    calls: list[tuple[object, list[str]]] = []

    def fake_atom(main, argv):
        calls.append((main, list(argv)))
        return {"ok": True, "validated": True}

    import lokay.fala_organ as fala_organ

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
    validated = handle_self_repair(
        "self_repair_validate", {}, {"self_repair_prepare": prepared}, ctx
    )
    committed = handle_self_repair(
        "self_repair_commit", {}, {"self_repair_prepare": prepared}, ctx
    )
    handle_self_repair(
        "self_repair_push_main",
        {},
        {
            "self_repair_prepare": prepared,
            "self_repair_validate": {"validated": True},
        },
        ctx,
    )

    assert agent["reason"] == "resume_existing_candidate"
    assert committed["reason"] == "resume_committed_candidate"
    assert calls == [
        (
            validate_module.main,
            ["--worktree", str(tmp_path), "--base-sha", "a" * 40],
        ),
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
    from lokay.proc import commit_all, self_repair_validate as validate_module

    calls: list[tuple[object, list[str]]] = []

    def fake_atom(main, argv):
        calls.append((main, list(argv)))
        return {"ok": True, "validated": True, "committed": True}

    import lokay.fala_organ as fala_organ

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
    handle_self_repair(
        "self_repair_validate", {}, {"self_repair_prepare": prepared}, ctx
    )
    handle_self_repair(
        "self_repair_commit",
        {"fingerprint": "deadbeef"},
        {"self_repair_prepare": prepared},
        ctx,
    )

    assert agent["reason"] == "resume_existing_candidate"
    assert calls == [
        (
            validate_module.main,
            ["--worktree", str(tmp_path), "--base-sha", "a" * 40],
        ),
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


def test_self_repair_validate_checks_dirty_and_staged_work_with_base(
    tmp_path, monkeypatch, capsys
):
    worktree = tmp_path / "wt"
    worktree.mkdir()
    checks: list[tuple[str, ...]] = []

    class FakeRun:
        def run_checked(self, spec, *, live):
            if spec.argv[1:3] == ("status", "--porcelain"):
                return SimpleNamespace(stdout=" M src/lokay/x.py\n", returncode=0)
            if spec.argv[1:3] == ("diff", "--name-only"):
                return SimpleNamespace(stdout="", returncode=0)
            raise AssertionError(spec.argv)

        def run(self, spec, *, live):
            if spec.argv[0] == "uv":
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            checks.append(spec.argv)
            return SimpleNamespace(
                returncode=(2 if spec.argv == ("git", "diff", "--check") else 0),
                stdout="",
                stderr="trailing whitespace",
            )

    monkeypatch.setattr(self_repair_validate, "runner", FakeRun)
    code = self_repair_validate.main(
        ["--worktree", str(worktree), "--base-sha", "a" * 40]
    )

    assert code == 1
    assert checks == [("git", "diff", "--check")]
    assert "diff check failed" in capsys.readouterr().out
