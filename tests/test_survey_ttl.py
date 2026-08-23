from pathlib import Path
import os
import time

from lokay.passkit import io as pass_io
from lokay.proc import survey_inbox, survey_prs
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


def test_recent_empty_stamp_skips_ready_catalog(tmp_path: Path) -> None:
    from lokay.proc.prepare_ready_survey import prepare

    stamp = tmp_path / "factory-survey.stamp"
    stamp.write_text("1", encoding="utf-8")
    out = prepare(pass_dir=_pass(tmp_path), slot_count=30)
    assert out["route"] == "skip" and out["repos"] == []


def test_pytest_does_not_skip_github_surveys_using_the_mill_stamp(
    tmp_path: Path, monkeypatch
) -> None:
    mill = tmp_path / ".lokay"
    mill.mkdir()
    stamp = mill / "factory-survey.stamp"
    stamp.write_text("1", encoding="utf-8")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv(
        "PYTEST_CURRENT_TEST",
        "test_pytest_does_not_skip_github_surveys_using_the_mill_stamp",
    )
    assert survey_ttl.survey_recently_empty(stamp) is False
    assert (
        survey_ttl.skip_idle_factory_pass(
            live=True,
            stamp=stamp,
            receipt={
                "health": "idle",
                "idle": True,
                "remaining": {"inbox": 0, "ready": 0, "open_ai_prs": 0},
            },
        )
        is None
    )
    hermetic = tmp_path / "factory-survey.stamp"
    hermetic.write_text("1", encoding="utf-8")
    assert survey_ttl.survey_recently_empty(hermetic) is True
    src = (
        Path(__file__).resolve().parents[1] / "src" / "lokay" / "proc" / "survey_ttl.py"
    )
    assert "Pytest must not skip GitHub surveys using the mill stamp." in src.read_text(
        encoding="utf-8"
    )


def test_pr_survey_expired_stamp_selects_probe(tmp_path: Path) -> None:
    from lokay.proc.prepare_pr_survey import prepare
    from lokay.proc.select_pr_survey_slot import select

    stamp = tmp_path / "factory-survey.stamp"
    stamp.write_text("1")
    old = time.time() - survey_ttl.SURVEY_TTL_SECONDS - 1
    os.utime(stamp, (old, old))
    prepared = prepare(pass_dir=_pass(tmp_path), slot_count=30)
    assert select(prepared, slot=1)["route"] == "survey"


def test_pr_survey_failed_listing_is_probe_failure():
    from lokay.proc.record_pr_survey_repo import record
    from lokay.proc.reduce_pr_survey import reduce_state

    row = record(
        {"mini_repo": "mikolaj92/lokay"},
        {"repo": "mikolaj92/lokay"},
        {
            "ok": True,
            "repo": "mikolaj92/lokay",
            "route": "failed",
            "listed": {"ok": False},
        },
    )
    state = reduce_state(
        prepared={}, rows=[row], working={"actions": [], "survey_errors": 0}
    )["state"]
    assert (
        state["pr_survey_failed"] == ["mikolaj92/lokay"] and state["survey_errors"] == 1
    )


def test_ready_stamp_update_touches_empty_and_clears_nonempty(tmp_path: Path) -> None:
    from lokay.proc.update_ready_survey_stamp import update

    pass_dir = _pass(tmp_path)
    stamp = tmp_path / "factory-survey.stamp"
    update(pass_dir=pass_dir, finalized={"skipped": False, "probe_failed": False})
    assert stamp.is_file()
    _, working = (
        pass_io.read_json(pass_io.begin_path(pass_dir)),
        pass_io.read_json(pass_io.working_path(pass_dir)),
    )
    working["remaining_ready"] = 1
    pass_io.write_json(pass_io.working_path(pass_dir), working)
    update(pass_dir=pass_dir, finalized={"skipped": False, "probe_failed": False})
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
    receipt = _idle_receipt(by_repo=[{"repo": "mikolaj92/lokay", "occupied": True}])
    assert (
        survey_ttl.skip_idle_factory_pass(live=True, stamp=stamp, receipt=receipt)
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

    assert (
        survey_ttl.mill_survey_still_empty(repo="mikolaj92/lokay", run=fake_run) is True
    )
    assert len(calls) == 3


def test_mill_survey_probe_ready_is_false() -> None:
    def fake_run(argv, **_k):
        joined = " ".join(argv)
        if "--label" in argv:
            return _gh_ok('[{"number": 12, "state": "OPEN"}]')
        return _gh_ok("[]")

    assert (
        survey_ttl.mill_survey_still_empty(repo="mikolaj92/lokay", run=fake_run)
        is False
    )


def test_mill_survey_probe_failure_is_none() -> None:
    def fake_run(argv, **_k):
        return type("R", (), {"returncode": 1, "stdout": "", "stderr": "boom"})()

    assert (
        survey_ttl.mill_survey_still_empty(repo="mikolaj92/lokay", run=fake_run) is None
    )


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


def test_live_daemon_cycle_always_hosts_authored_fala(monkeypatch, tmp_path):
    from lokay.compose import daemon_cycle as daemon_mod

    called = []
    monkeypatch.setattr(daemon_mod, "rotate_mill_fala_journals", lambda: {"ok": True})
    monkeypatch.setattr(
        daemon_mod, "trusted_fala_manifest", lambda: tmp_path / "pkg.toml"
    )
    monkeypatch.setattr(
        daemon_mod,
        "run_path",
        lambda **kwargs: called.append(kwargs) or {"ok": True, "health": "idle"},
    )
    out = daemon_mod.compose_daemon_cycle(config_path="config.yaml", max_passes=1)
    assert out["health"] == "idle" and called[0]["path_id"] == "daemon_cycle"
