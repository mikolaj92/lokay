"""Hermetic tests for lokay.proc.unbounded_detect (JSON stdin/stdout)."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

from lokay.proc.unbounded_detect import detect, main, run_detect

ROOT = Path(__file__).resolve().parents[1]


def _cli(monkeypatch, capsys, payload: dict | str | None) -> tuple[int, dict]:
    raw = "" if payload is None else (
        payload if isinstance(payload, str) else json.dumps(payload)
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO(raw))
    code = main([])
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    return code, out


def test_full_corpus_is_unbounded():
    out = detect("Ingest the full corpus", "Sejm sitting texts, no cap.")
    assert out["unbounded"] is True
    assert out["reason"] == "full_corpus"


def test_korpus_sejmu_is_unbounded():
    out = detect("Korpus Sejmu", "Zbierz wypowiedzi.")
    assert out["unbounded"] is True
    assert out["reason"] == "full_corpus"


def test_fill_history_is_unbounded():
    out = detect("Fill history", "Napełnij historię głosowań.")
    assert out["unbounded"] is True
    assert out["reason"] == "fill_history"


def test_napelnij_historie_is_unbounded():
    out = detect("Napełnij historię", "Uzupełnij brakujące kadencje.")
    assert out["unbounded"] is True
    assert out["reason"] == "fill_history"


def test_zbierz_wszystko_is_unbounded():
    out = detect("Zbierz wszystko", "Pobierz każde posiedzenie.")
    assert out["unbounded"] is True
    assert out["reason"] == "collect_everything"


def test_collect_everything_english_is_unbounded():
    out = detect("Collect everything", "Gather all records from the archive.")
    assert out["unbounded"] is True
    assert out["reason"] == "collect_everything"


def test_open_months_is_unbounded():
    out = detect("Long scrape", "This collection takes months.")
    assert out["unbounded"] is True
    assert out["reason"] == "open_duration"


def test_bez_stropu_is_unbounded():
    out = detect("Zadanie bez stropu", "Nie ma limitu.")
    assert out["unbounded"] is True
    assert out["reason"] == "no_upper_bound"


def test_empty_spec_fail_closed():
    out = detect("", "   ")
    assert out["unbounded"] is True
    assert out["reason"] == "empty_spec"


def test_no_finite_done_condition_fail_closed():
    out = detect("Improve things", "Make it better somehow.")
    assert out["unbounded"] is True
    assert out["reason"] == "no_finite_done_condition"


def test_collection_without_cap_fail_closed():
    out = detect("Scrape sittings", "Ingest the archive as it grows.")
    assert out["unbounded"] is True
    assert out["reason"] == "no_finite_done_condition"


def test_done_means_is_bounded():
    out = detect(
        "Add unbounded_detect atom",
        "Done means: CLI reads title+body JSON and prints unbounded+reason.",
    )
    assert out["unbounded"] is False
    assert out["reason"] == "finite_done_condition"


def test_numeric_cap_bounds_full_corpus():
    out = detect(
        "Ingest the full corpus",
        "First 100 sittings only. Cap 100 documents.",
    )
    assert out["unbounded"] is False
    assert out["reason"] == "numeric_cap"


def test_lookback_window_bounds_history_fill():
    out = detect("Fill history", "Backfill the last 7 days of votes.")
    assert out["unbounded"] is False
    assert out["reason"] == "lookback_window"


def test_checkbox_done_condition_is_bounded():
    out = detect(
        "Ship the atom",
        "- [ ] add src/lokay/proc/unbounded_detect.py\n- [ ] add tests\n",
    )
    assert out["unbounded"] is False
    assert out["reason"] == "checkbox_done_condition"


def test_finite_code_change_is_bounded():
    out = detect("Fix parser edge case", "Handle empty input in `src/parse.py`.")
    assert out["unbounded"] is False
    assert out["reason"] == "finite_change"


def test_history_in_ui_copy_is_not_collection():
    out = detect("Fix login history page", "Show the last event in the settings UI.")
    assert out["unbounded"] is False
    assert out["reason"] == "finite_change"


def test_fix_without_path_is_still_finite():
    out = detect("Fix parser", "Handle empty input.")
    assert out["unbounded"] is False
    assert out["reason"] == "finite_change"


def test_run_detect_envelope():
    env = run_detect({"title": "Zbierz wszystko", "body": ""})
    assert env["ok"] is True
    assert env["unbounded"] is True
    assert env["reason"] == "collect_everything"


def test_run_detect_rejects_non_object():
    env = run_detect(["nope"])
    assert env["ok"] is False


def test_cli_unbounded_stdout(monkeypatch, capsys):
    code, out = _cli(
        monkeypatch,
        capsys,
        {"title": "full corpus dump", "body": "no limit given"},
    )
    assert code == 0
    assert out["ok"] is True
    assert out["unbounded"] is True
    assert out["reason"] == "full_corpus"


def test_cli_bounded_stdout(monkeypatch, capsys):
    code, out = _cli(
        monkeypatch,
        capsys,
        {
            "title": "Fix parser",
            "body": "Handle empty input.\nDone means: empty string returns [].",
        },
    )
    assert code == 0
    assert out["ok"] is True
    assert out["unbounded"] is False


def test_cli_empty_stdin_fail_closed(monkeypatch, capsys):
    code, out = _cli(monkeypatch, capsys, None)
    assert code == 0
    assert out["unbounded"] is True
    assert out["reason"] == "empty_spec"


def test_cli_invalid_json_errors(monkeypatch, capsys):
    code, out = _cli(monkeypatch, capsys, "{not json")
    assert code == 1
    assert out["ok"] is False


def test_module_cli_python_m():
    proc = subprocess.run(
        [sys.executable, "-m", "lokay.proc.unbounded_detect"],
        input=json.dumps(
            {"title": "Zbierz wszystko", "body": "Pobierz każde posiedzenie."}
        ),
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout.strip().splitlines()[-1])
    assert out["unbounded"] is True
    assert out["reason"] == "collect_everything"
