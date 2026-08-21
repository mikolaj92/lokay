from pathlib import Path
import os
import time

from lokay.passkit import io as pass_io
from lokay.proc import survey_inbox, survey_prs, survey_ready
from lokay.proc import survey_ttl


def _pass(tmp_path: Path, *, remaining_prs: int = 0, remaining_inbox: int = 0) -> str:
    pass_dir = tmp_path / "pass"
    pass_dir.mkdir()
    pass_io.write_json(
        pass_io.begin_path(pass_dir),
        {
            "live": True,
            "repos": ["mikolaj92/lokay"],
            "state_path": str(tmp_path / "state.jsonl"),
            "stuck_path": str(tmp_path / "stuck.json"),
        },
    )
    pass_io.write_json(
        pass_io.working_path(pass_dir),
        {
            "actions": [],
            "survey_errors": 0,
            "remaining_prs": remaining_prs,
            "remaining_inbox": remaining_inbox,
            "prs_by_repo": {},
            "inbox_by_repo": {},
            "inbox_issues_by_repo": {},
        },
    )
    return str(pass_dir)


def test_empty_ready_survey_writes_stamp(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        survey_ready,
        "run_proc",
        lambda *_a, **_k: {"ok": True, "issues": []},
    )
    out = survey_ready.run_survey_ready(
        pass_dir=_pass(tmp_path), config_path=None, live=True
    )
    assert out["ok"] is True
    assert (tmp_path / "factory-survey.stamp").is_file()


def test_surveys_skip_github_when_recent_empty_stamp(tmp_path: Path, monkeypatch) -> None:
    stamp = tmp_path / "factory-survey.stamp"
    stamp.write_text("1", encoding="utf-8")
    before = stamp.stat().st_mtime

    def boom(*_a, **_k):
        raise AssertionError("recent empty factory survey must not list GitHub")

    monkeypatch.setattr(survey_prs, "run_proc", boom)
    monkeypatch.setattr(survey_inbox, "run_proc", boom)
    monkeypatch.setattr(survey_ready, "run_proc", boom)
    pass_dir = _pass(tmp_path)
    prs = survey_prs.run_survey_prs(pass_dir=pass_dir, config_path=None, live=True)
    inbox = survey_inbox.run_survey_inbox(pass_dir=pass_dir, config_path=None, live=True)
    ready = survey_ready.run_survey_ready(pass_dir=pass_dir, config_path=None, live=True)
    assert prs["skipped"] is True
    assert inbox["skipped"] is True
    assert ready["skipped"] is True
    assert stamp.stat().st_mtime == before


def test_survey_probes_when_empty_stamp_expired(tmp_path: Path, monkeypatch) -> None:
    stamp = tmp_path / "factory-survey.stamp"
    stamp.write_text("1", encoding="utf-8")
    old = time.time() - survey_ttl.SURVEY_TTL_SECONDS - 1
    os.utime(stamp, (old, old))
    called: list[str] = []

    def listed(*_a, **_k):
        called.append("prs")
        return {"ok": True, "prs": []}

    monkeypatch.setattr(survey_prs, "run_proc", listed)
    out = survey_prs.run_survey_prs(
        pass_dir=_pass(tmp_path), config_path=None, live=True
    )
    assert out.get("skipped") is not True
    assert called == ["prs"]


def test_ready_ttl_flag_does_not_skip_later_repos(tmp_path: Path, monkeypatch) -> None:
    """Covered PRs in repo A must not reuse the TTL skip flag for repo B."""
    pass_dir = tmp_path / "pass"
    pass_dir.mkdir()
    pass_io.write_json(
        pass_io.begin_path(pass_dir),
        {
            "live": True,
            "repos": ["a/one", "a/two"],
            "state_path": str(tmp_path / "state.jsonl"),
            "branch_prefix": "ai/fix/",
        },
    )
    pass_io.write_json(
        pass_io.working_path(pass_dir),
        {
            "actions": [],
            "survey_errors": 0,
            "remaining_prs": 1,
            "remaining_inbox": 0,
            "prs_by_repo": {
                "a/one": [{"number": 1, "head_ref": "ai/fix/1-x"}],
                "a/two": [],
            },
        },
    )
    listed: list[str] = []

    def fake_run(fn, argv):
        repo = argv[argv.index("--repo") + 1]
        if "--issue" in argv:
            return {"ok": True, "issue": {"number": int(argv[argv.index("--issue") + 1]), "state": "OPEN"}}
        listed.append(repo)
        if repo == "a/two":
            return {"ok": True, "issues": [{"number": 2, "repo": repo, "labels": ["work:ready"]}]}
        return {"ok": True, "issues": []}

    monkeypatch.setattr(survey_ready, "run_proc", fake_run)
    out = survey_ready.run_survey_ready(
        pass_dir=str(pass_dir), config_path=None, live=True
    )
    assert listed == ["a/one", "a/two"]
    assert out["remaining_ready"] == 1
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    assert [issue["number"] for issue in working["ready_by_repo"]["a/two"]] == [2]


def test_nonempty_ready_clears_stamp(tmp_path: Path, monkeypatch) -> None:
    stamp = tmp_path / "factory-survey.stamp"
    stamp.write_text("1", encoding="utf-8")
    old = time.time() - survey_ttl.SURVEY_TTL_SECONDS - 1
    os.utime(stamp, (old, old))
    monkeypatch.setattr(
        survey_ready,
        "run_proc",
        lambda fn, argv: (
            {
                "ok": True,
                "issue": {"number": 12, "state": "OPEN"},
            }
            if "--issue" in argv
            else {"ok": True, "issues": [{"number": 12}]}
        ),
    )
    out = survey_ready.run_survey_ready(
        pass_dir=_pass(tmp_path), config_path=None, live=True
    )
    assert out["remaining_ready"] == 1
    assert not stamp.exists()


def _idle_receipt(**remaining):
    base = {
        "inbox": 0,
        "ready": 0,
        "open_ai_prs": 0,
        "issue_to_pr_started": 0,
        "survey_errors": 0,
        "by_repo": [{"repo": "mikolaj92/lokay", "occupied": False}],
    }
    base.update(remaining)
    return {"health": "idle", "idle": True, "remaining": base}


def test_skip_idle_factory_pass_does_not_refresh_stamp(tmp_path: Path) -> None:
    stamp = tmp_path / "factory-survey.stamp"
    stamp.write_text("1", encoding="utf-8")
    before = stamp.stat().st_mtime
    out = survey_ttl.skip_idle_factory_pass(
        live=True, stamp=stamp, receipt=_idle_receipt()
    )
    assert out is not None
    assert out["skipped"] is True
    assert out["reason"] == "recent_empty_survey"
    assert out["health"] == "idle"
    assert stamp.stat().st_mtime == before


def test_skip_idle_factory_pass_hosts_when_stamp_missing(tmp_path: Path) -> None:
    stamp = tmp_path / "factory-survey.stamp"
    assert (
        survey_ttl.skip_idle_factory_pass(
            live=True, stamp=stamp, receipt=_idle_receipt()
        )
        is None
    )


def test_skip_idle_factory_pass_hosts_when_occupied(tmp_path: Path) -> None:
    stamp = tmp_path / "factory-survey.stamp"
    stamp.write_text("1", encoding="utf-8")
    receipt = _idle_receipt(
        by_repo=[{"repo": "mikolaj92/lokay", "occupied": True}]
    )
    assert (
        survey_ttl.skip_idle_factory_pass(
            live=True, stamp=stamp, receipt=receipt
        )
        is None
    )


def test_skip_idle_factory_pass_hosts_when_ready(tmp_path: Path) -> None:
    stamp = tmp_path / "factory-survey.stamp"
    stamp.write_text("1", encoding="utf-8")
    assert (
        survey_ttl.skip_idle_factory_pass(
            live=True, stamp=stamp, receipt=_idle_receipt(ready=1)
        )
        is None
    )


def test_expired_stamp_empty_probe_skips_and_refreshes(tmp_path: Path) -> None:
    stamp = tmp_path / "factory-survey.stamp"
    stamp.write_text("1", encoding="utf-8")
    old = time.time() - survey_ttl.SURVEY_TTL_SECONDS - 1
    os.utime(stamp, (old, old))
    out = survey_ttl.skip_idle_factory_pass(
        live=True,
        stamp=stamp,
        receipt=_idle_receipt(),
        probe=lambda: True,
    )
    assert out is not None
    assert out["skipped"] is True
    assert out["reason"] == "recent_empty_survey_probe"
    assert stamp.stat().st_mtime >= old + survey_ttl.SURVEY_TTL_SECONDS


def test_expired_stamp_probe_failure_hosts(tmp_path: Path) -> None:
    stamp = tmp_path / "factory-survey.stamp"
    stamp.write_text("1", encoding="utf-8")
    old = time.time() - survey_ttl.SURVEY_TTL_SECONDS - 1
    os.utime(stamp, (old, old))
    assert (
        survey_ttl.skip_idle_factory_pass(
            live=True,
            stamp=stamp,
            receipt=_idle_receipt(),
            probe=lambda: None,
        )
        is None
    )
    assert stamp.stat().st_mtime == old


def test_expired_stamp_remaining_work_hosts(tmp_path: Path) -> None:
    stamp = tmp_path / "factory-survey.stamp"
    stamp.write_text("1", encoding="utf-8")
    old = time.time() - survey_ttl.SURVEY_TTL_SECONDS - 1
    os.utime(stamp, (old, old))
    assert (
        survey_ttl.skip_idle_factory_pass(
            live=True,
            stamp=stamp,
            receipt=_idle_receipt(),
            probe=lambda: False,
        )
        is None
    )
    assert stamp.stat().st_mtime == old


def _gh_ok(stdout: str):
    return type("R", (), {"returncode": 0, "stdout": stdout, "stderr": ""})()


def test_mill_survey_probe_empty_is_true() -> None:
    calls: list[str] = []

    def fake_run(argv, **_k):
        calls.append(" ".join(argv))
        return _gh_ok("[]")

    assert survey_ttl.mill_survey_still_empty(repo="mikolaj92/lokay", run=fake_run) is True
    assert len(calls) == 3


def test_mill_survey_probe_ready_is_false() -> None:
    def fake_run(argv, **_k):
        joined = " ".join(argv)
        if "--label" in argv:
            return _gh_ok('[{"number": 12, "state": "OPEN"}]')
        return _gh_ok("[]")

    assert survey_ttl.mill_survey_still_empty(repo="mikolaj92/lokay", run=fake_run) is False


def test_mill_survey_probe_failure_is_none() -> None:
    def fake_run(argv, **_k):
        return type("R", (), {"returncode": 1, "stdout": "", "stderr": "boom"})()

    assert survey_ttl.mill_survey_still_empty(repo="mikolaj92/lokay", run=fake_run) is None


def test_live_idle_daemon_cycle_skips_fala(monkeypatch, tmp_path: Path) -> None:
    from lokay.compose import daemon_cycle as daemon_mod

    stamp = tmp_path / "factory-survey.stamp"
    stamp.write_text("1", encoding="utf-8")
    before = stamp.stat().st_mtime
    leftover = {
        "ok": True,
        "labels_removed": False,
        "leftover_closed": 0,
        "skipped": True,
        "reason": "recent_empty",
    }

    def boom(**_kwargs):
        raise AssertionError("idle mill must not host daemon_cycle Fala")

    monkeypatch.delenv("LOKAY_OFFLINE", raising=False)
    monkeypatch.setattr(daemon_mod, "rotate_mill_fala_journals", lambda: {"ok": True})
    monkeypatch.setattr(daemon_mod, "run_path", boom)
    monkeypatch.setattr(daemon_mod, "trusted_fala_manifest", lambda: tmp_path / "pkg.toml")
    monkeypatch.setattr(
        daemon_mod,
        "skip_idle_factory_pass",
        lambda **_k: {
            "ok": True,
            "health": "idle",
            "idle": True,
            "live": True,
            "progress": 0,
            "remaining": {"ready": 0, "inbox": 0, "open_ai_prs": 0},
            "skipped": True,
            "reason": "recent_empty_survey",
        },
    )
    harvested: list[dict] = []

    def fake_harvest(**kwargs):
        harvested.append(kwargs)

    monkeypatch.setattr(daemon_mod, "harvest_idle_mill_stuck", fake_harvest)
    reaped: list[dict] = []

    def fake_reap(**kwargs):
        reaped.append(kwargs)

    monkeypatch.setattr(daemon_mod, "reap_idle_closed_worktrees", fake_reap)
    monkeypatch.setattr(daemon_mod, "run_closeout_leftover", lambda **_k: leftover)
    out = daemon_mod.compose_daemon_cycle(
        config_path=str(tmp_path / "config.yaml"),
        pass_ceiling_seconds=5,
    )
    assert out["ok"] is True
    assert out["skipped"] is True
    assert out["engine"] == "fala"
    assert out["path_id"] == "daemon_cycle"
    assert out["leftover_closeout"] == leftover
    assert harvested == [
        {"config_path": str(tmp_path / "config.yaml"), "live": True}
    ]
    assert reaped == [
        {"config_path": str(tmp_path / "config.yaml"), "live": True}
    ]
    assert stamp.stat().st_mtime == before


def test_live_idle_daemon_cycle_hosts_when_stamp_missing(
    monkeypatch, tmp_path: Path
) -> None:
    from lokay.compose import daemon_cycle as daemon_mod

    called: list[str] = []

    def fake_run(**_kwargs):
        called.append("run")
        return {"ok": True, "health": "idle"}

    monkeypatch.delenv("LOKAY_OFFLINE", raising=False)
    monkeypatch.setattr(daemon_mod, "rotate_mill_fala_journals", lambda: {"ok": True})
    monkeypatch.setattr(daemon_mod, "run_path", fake_run)
    monkeypatch.setattr(daemon_mod, "trusted_fala_manifest", lambda: tmp_path / "pkg.toml")
    monkeypatch.setattr(daemon_mod, "skip_idle_factory_pass", lambda **_k: None)

    def leftover_boom(**_kwargs):
        raise AssertionError("hosting daemon_cycle must not short-circuit leftover via skip")

    monkeypatch.setattr(daemon_mod, "run_closeout_leftover", leftover_boom)
    out = daemon_mod.compose_daemon_cycle(
        config_path=str(tmp_path / "config.yaml"),
        pass_ceiling_seconds=5,
    )
    assert called == ["run"]
    assert out["ok"] is True
    assert out.get("skipped") is not True


def test_live_idle_factory_pass_skips_fala(monkeypatch, tmp_path: Path) -> None:
    from lokay.compose import factory as factory_mod

    stamp = tmp_path / "factory-survey.stamp"
    stamp.write_text("1", encoding="utf-8")

    def boom(**_kwargs):
        raise AssertionError("idle mill must not host factory_pass Fala")

    monkeypatch.delenv("LOKAY_OFFLINE", raising=False)
    monkeypatch.setattr(factory_mod, "run_path", boom)
    monkeypatch.setattr(
        factory_mod,
        "skip_idle_factory_pass",
        lambda **_k: {
            "ok": True,
            "health": "idle",
            "idle": True,
            "live": True,
            "progress": 0,
            "remaining": {"ready": 0, "inbox": 0},
            "skipped": True,
            "reason": "recent_empty_survey",
        },
    )
    out = factory_mod.compose_factory_pass(
        config_path="config.yaml", live=True, db_path=str(tmp_path / "factory")
    )
    assert out["ok"] is True
    assert out["skipped"] is True
    assert out["engine"] == "fala"
    assert out["kind"] == "factory_pass"
