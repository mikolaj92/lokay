from pathlib import Path

from lokay.passkit import io as pass_io
from lokay.proc import dispatch_triage


def _pass_dir(tmp_path: Path, *, stuck_path: Path) -> Path:
    pass_dir = tmp_path / "pass"
    pass_dir.mkdir()
    pass_io.write_json(
        pass_io.begin_path(pass_dir),
        {"stuck_path": str(stuck_path), "live": True},
    )
    pass_io.write_json(
        pass_io.plan_path(pass_dir),
        {
            "triage_targets": [
                {"repo": "owner/repo", "issue": 1},
                {"repo": "owner/repo", "issue": 2},
            ]
        },
    )
    pass_io.write_json(
        pass_io.working_path(pass_dir),
        {"actions": [], "progress": 0, "remaining_inbox": 2, "inbox_by_repo": {"owner/repo": 2}},
    )
    return pass_dir


def test_dispatch_triage_skips_blocked_target_but_runs_other(tmp_path, monkeypatch):
    stuck_path = tmp_path / "stuck.json"
    stuck_path.write_text(
        '{"issues": {"owner/repo#1": {"blocked": true}}}\n', encoding="utf-8"
    )
    pass_dir = _pass_dir(tmp_path, stuck_path=stuck_path)
    calls = []

    def fake_run_path(**kwargs):
        calls.append(kwargs)
        return {"ok": True, "applied": True}

    monkeypatch.setattr(dispatch_triage, "run_path", fake_run_path)

    result = dispatch_triage.run_dispatch_triage(
        pass_dir=str(pass_dir), config_path=None, live=True
    )

    assert result["ok"] is True
    assert result["ran"] == 1
    assert calls == [
        {
            "path_id": "issue_triage",
            "repo": "owner/repo",
            "issue": 2,
            "config_path": None,
            "live": True,
        }
    ]
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    blocked = next(
        action
        for action in working["actions"]
        if action.get("issue") == 1
    )
    assert blocked["skipped"] is True
    assert blocked["blocked"] is True
    assert blocked["reason"] == "blocked_in_stuck_ledger"
    assert working["progress"] == 1
    assert working["remaining_inbox"] == 1
