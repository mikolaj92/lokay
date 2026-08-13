"""Hermetic stall_cause: last-pass fixture JSON → one-line cause."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from lokay.proc.stall_cause import cause_line, main


def _write(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _run(path: Path, capsys) -> tuple[int, str, str]:
    code = main(["--file", str(path)])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_missing_file_exits_2(tmp_path: Path, capsys):
    missing = tmp_path / "nope.json"
    code, out, err = _run(missing, capsys)
    assert code == 2
    assert out == ""
    assert "missing last-pass json" in err


def test_pi_over_budget_field(tmp_path: Path, capsys):
    path = _write(tmp_path / "last-pass.json", {"pi_over_budget": True, "health": "stall"})
    code, out, err = _run(path, capsys)
    assert code == 0
    assert err == ""
    assert out == "pi over budget\n"


def test_plan_only_diff_field(tmp_path: Path, capsys):
    path = _write(tmp_path / "last-pass.json", {"plan_only_diff": True})
    code, out, _err = _run(path, capsys)
    assert code == 0
    assert out == "plan-only diff\n"


def test_host_behind_origin_main_field(tmp_path: Path, capsys):
    path = _write(tmp_path / "last-pass.json", {"host_behind_origin_main": True})
    code, out, _err = _run(path, capsys)
    assert code == 0
    assert out == "host behind origin/main\n"


def test_llm_review_blocked_merge_field(tmp_path: Path, capsys):
    path = _write(tmp_path / "last-pass.json", {"llm_review_blocked_merge": True})
    code, out, _err = _run(path, capsys)
    assert code == 0
    assert out == "llm review blocked merge\n"


def test_most_specific_field_wins(tmp_path: Path, capsys):
    path = _write(
        tmp_path / "last-pass.json",
        {
            "health": "stall",
            "llm_review_blocked_merge": True,
            "host_behind_origin_main": True,
            "plan_only_diff": True,
            "pi_over_budget": True,
            "remaining": {"review_limbo": 3, "needs_repair": 1},
        },
    )
    code, out, _err = _run(path, capsys)
    assert code == 0
    assert out == "pi over budget\n"


def test_nested_named_field_wins_over_remaining(tmp_path: Path, capsys):
    path = _write(
        tmp_path / "last-pass.json",
        {
            "health": "stall",
            "remaining": {
                "plan_only_diff": True,
                "review_limbo": 2,
                "needs_repair": 1,
            },
            "require_llm_review": True,
        },
    )
    code, out, _err = _run(path, capsys)
    assert code == 0
    assert out == "plan-only diff\n"


def test_error_phrase_host_behind(tmp_path: Path, capsys):
    path = _write(
        tmp_path / "last-pass.json",
        {"ok": False, "error": "refusing tick: host behind origin/main"},
    )
    code, out, _err = _run(path, capsys)
    assert code == 0
    assert out == "host behind origin/main\n"


def test_reason_zero_diff_is_plan_only(tmp_path: Path, capsys):
    path = _write(
        tmp_path / "last-pass.json",
        {"ok": False, "reason": "zero_diff", "error": "no new commit to publish"},
    )
    code, out, _err = _run(path, capsys)
    assert code == 0
    assert out == "plan-only diff\n"


def test_review_limbo_infers_llm_review(tmp_path: Path, capsys):
    path = _write(
        tmp_path / "last-pass.json",
        {
            "health": "waiting",
            "require_llm_review": True,
            "merge_enabled": True,
            "remaining": {"review_limbo": 1, "open_ai_prs": 1},
        },
    )
    code, out, _err = _run(path, capsys)
    assert code == 0
    assert out == "llm review blocked merge\n"


def test_idle_health_fallback(tmp_path: Path, capsys):
    path = _write(
        tmp_path / "last-pass.json",
        {"kind": "pass_receipt", "health": "idle", "idle": True, "remaining": {}},
    )
    code, out, _err = _run(path, capsys)
    assert code == 0
    assert out == "idle\n"


def test_default_home_path(tmp_path: Path, monkeypatch, capsys):
    home = tmp_path / "home"
    (home / ".lokay").mkdir(parents=True)
    _write(home / ".lokay" / "last-pass.json", {"pi_over_budget": True})
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    code = main([])
    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == "pi over budget\n"


def test_unreadable_json_exits_1(tmp_path: Path, capsys):
    path = tmp_path / "last-pass.json"
    path.write_text("{not json", encoding="utf-8")
    code, out, err = _run(path, capsys)
    assert code == 1
    assert out == ""
    assert "unreadable last-pass json" in err


def test_module_cli_with_file(tmp_path: Path):
    path = _write(tmp_path / "last-pass.json", {"host_behind_origin_main": True})
    result = subprocess.run(
        [sys.executable, "-m", "lokay.proc.stall_cause", "--file", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout == "host behind origin/main\n"


def test_cause_line_pure():
    assert cause_line({"pi_over_budget": 1, "plan_only_diff": True}) == "pi over budget"
    assert cause_line({"reason": "llm_review_not_approved"}) == "llm review blocked merge"
    assert cause_line({"health": "progress", "progress": 2}) == "progress"
