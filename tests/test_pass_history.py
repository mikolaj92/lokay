import json
from pathlib import Path

from lokay.pass_history import append_pass_receipt, read_pass_history


def test_pass_history_is_newest_first_bounded_and_skips_malformed(tmp_path: Path):
    state = tmp_path / "state.jsonl"
    for number in range(4):
        append_pass_receipt({"ts": str(number), "progress": number}, state_path=state, limit=3)
    path = tmp_path / "pass-history.jsonl"
    assert len(path.read_text().splitlines()) == 3
    path.write_text("bad\n" + path.read_text(), encoding="utf-8")
    assert [row["ts"] for row in read_pass_history(state_path=state, limit=10)] == ["3", "2", "1"]


def test_record_pass_appends_history(tmp_path: Path):
    from lokay.passkit import io as pass_io
    from lokay.proc.record_pass import run_record_pass

    pass_dir = tmp_path / "pass"
    pass_dir.mkdir()
    state = tmp_path / "state.jsonl"
    pass_io.write_json(pass_io.begin_path(pass_dir), {
        "merge_enabled": True,
        "require_checks": False,
        "require_llm_review": True,
        "max_issue_to_pr_per_pass": 1,
        "config_path": str(tmp_path / "config.yaml"),
        "state_path": str(state),
    })
    pass_io.write_json(pass_io.tick_path(pass_dir), {
        "ok": True, "health": "progress", "progress": 1,
        "remaining": {"inbox": 0, "ready": 1, "open_ai_prs": 0},
    })
    result = run_record_pass(pass_dir=str(pass_dir))
    assert result["ok"] is True
    assert read_pass_history(state_path=state)[0]["progress"] == 1
