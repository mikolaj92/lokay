"""Hermetic tests for lokay-trace-event (one JSONL mill-step line)."""

from __future__ import annotations

import json
from pathlib import Path

from lokay.proc import trace_event


def _payload(capsys) -> dict:
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def _lines(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    assert text.endswith("\n")
    return [json.loads(line) for line in text.splitlines() if line]


def test_appends_one_json_line(tmp_path: Path, capsys):
    dest = tmp_path / "trace.jsonl"
    code = trace_event.main(
        [
            "--atom",
            "survey_prs",
            "--repo",
            "a/b",
            "--issue",
            "12",
            "--ok",
            "--file",
            str(dest),
        ]
    )
    assert code == 0
    payload = _payload(capsys)
    assert payload["ok"] is True
    assert payload["file"] == str(dest)
    rows = _lines(dest)
    assert len(rows) == 1
    row = rows[0]
    assert set(row) == {"ts", "atom", "repo", "issue", "ok", "error"}
    assert row["atom"] == "survey_prs"
    assert row["repo"] == "a/b"
    assert row["issue"] == 12
    assert row["ok"] is True
    assert row["error"] is None
    assert isinstance(row["ts"], str) and "T" in row["ts"]
    assert payload["event"] == row


def test_appends_second_line_does_not_overwrite(tmp_path: Path, capsys):
    dest = tmp_path / "nested" / "trace.jsonl"
    assert trace_event.main(["--atom", "plan_pass", "--file", str(dest)]) == 0
    assert (
        trace_event.main(
            [
                "--atom",
                "dispatch_implement",
                "--fail",
                "--error",
                "stuck at implement",
                "--file",
                str(dest),
            ]
        )
        == 0
    )
    capsys.readouterr()
    rows = _lines(dest)
    assert [r["atom"] for r in rows] == ["plan_pass", "dispatch_implement"]
    assert rows[0]["ok"] is True
    assert rows[1]["ok"] is False
    assert rows[1]["error"] == "stuck at implement"


def test_fail_write_still_emits_envelope_ok(tmp_path: Path, capsys):
    dest = tmp_path / "trace.jsonl"
    code = trace_event.main(
        ["--atom", "dispatch_implement", "--fail", "--file", str(dest)]
    )
    assert code == 0
    payload = _payload(capsys)
    assert payload["ok"] is True
    assert payload["event"]["ok"] is False
    assert _lines(dest)[0]["ok"] is False


def test_optional_fields_are_null(tmp_path: Path, capsys):
    dest = tmp_path / "trace.jsonl"
    code = trace_event.main(["--atom", "wake", "--file", str(dest)])
    assert code == 0
    _payload(capsys)
    row = _lines(dest)[0]
    assert row["atom"] == "wake"
    assert row["repo"] is None
    assert row["issue"] is None
    assert row["error"] is None
    assert row["ok"] is True


def test_empty_atom_fails_closed(tmp_path: Path, capsys):
    dest = tmp_path / "trace.jsonl"
    code = trace_event.main(["--atom", "  ", "--file", str(dest)])
    assert code == 1
    payload = _payload(capsys)
    assert payload["ok"] is False
    assert payload["error"] == "atom required"
    assert not dest.exists()


def test_write_failure_is_envelope_err(tmp_path: Path, capsys):
    dest = tmp_path / "not_a_file"
    dest.mkdir()
    code = trace_event.main(["--atom", "survey_inbox", "--file", str(dest)])
    assert code == 1
    payload = _payload(capsys)
    assert payload["ok"] is False
    assert payload.get("error")
    assert payload.get("file") == str(dest)


def test_default_file_is_home_lokay_trace_jsonl(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr(trace_event.Path, "home", lambda *a, **k: tmp_path)
    code = trace_event.main(["--atom", "factory_begin"])
    assert code == 0
    dest = tmp_path / ".lokay" / "trace.jsonl"
    assert dest.is_file()
    payload = _payload(capsys)
    assert payload["file"] == str(dest)
    assert _lines(dest)[0]["atom"] == "factory_begin"
