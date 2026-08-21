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
