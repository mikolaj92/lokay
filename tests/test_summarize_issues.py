import json

from lokay.proc.summarize_issues import envelope, summarize


def _receipt(path):
    return json.loads(path.joinpath("issues-receipt.json").read_text(encoding="utf-8"))


def test_envelope_is_ok_on_empty():
    out = envelope({"route": "none", "reason": "empty"}, {"route": "skip", "reason": "no_issue"}, {})
    assert out["ok"] is True
    assert out["result"]["route"] == "skip"
    assert out["result"]["reason"] == "no_issue"
    assert out["result"]["leftover"] == 0
    assert out["result"]["launched"] is None


def test_envelope_is_ok_on_overflow():
    out = envelope(
        {"route": "none", "reason": "overflow"},
        {"route": "skip", "reason": "no_issue"},
        {},
    )
    assert out["ok"] is True
    assert out["result"]["route"] == "skip"
    assert out["result"]["leftover"] == 0


def test_envelope_records_leftover_without_failing():
    out = envelope(
        {"route": "issue", "repo": "o/r", "issue": 2, "leftover": 1},
        {"route": "do", "repo": "o/r", "issue": 2},
        {"route": "started"},
    )
    assert out["ok"] is True
    assert out["result"]["leftover"] == 1
    assert out["result"]["launched"] == "started"
    assert out["result"]["issue"] == 2


def test_summarize_writes_receipt_on_empty(tmp_path):
    out = summarize(
        {"route": "none", "reason": "empty"},
        {"route": "skip", "reason": "no_issue"},
        {},
        pass_dir=str(tmp_path),
    )
    assert out["ok"] is True
    assert out["applied"] is True
    receipt = _receipt(tmp_path)
    assert receipt["route"] == "skip"
    assert receipt["leftover"] == 0
    assert out["result"]["receipt"] == str(tmp_path / "issues-receipt.json")


def test_summarize_writes_receipt_on_sito_skip(tmp_path):
    out = summarize(
        {"route": "issue", "repo": "o/r", "issue": 2},
        {"route": "skip", "reason": "sito_nie_robic", "repo": "o/r", "issue": 2},
        {},
        pass_dir=str(tmp_path),
    )
    assert out["ok"] is True
    receipt = _receipt(tmp_path)
    assert receipt["route"] == "skip"
    assert receipt["reason"] == "sito_nie_robic"
    assert receipt["issue"] == 2
    assert receipt["launched"] is None


def test_leftover_does_not_fail_the_pass(tmp_path):
    out = summarize(
        {"route": "issue", "repo": "o/r", "issue": 2, "leftover": 1},
        {"route": "do", "repo": "o/r", "issue": 2},
        {"route": "started"},
        pass_dir=str(tmp_path),
    )
    assert out["ok"] is True
    receipt = _receipt(tmp_path)
    assert receipt["leftover"] == 1
    assert receipt["route"] == "do"
    assert receipt["launched"] == "started"


def test_overflow_does_not_fail_the_pass(tmp_path):
    out = summarize(
        {"route": "none", "reason": "overflow"},
        {"route": "skip", "reason": "no_issue"},
        {},
        pass_dir=str(tmp_path),
    )
    assert out["ok"] is True
    assert tmp_path.joinpath("issues-receipt.json").is_file()
    assert _receipt(tmp_path)["route"] == "skip"


def test_summarize_without_pass_dir_does_not_write(tmp_path):
    out = summarize(
        {"route": "none", "reason": "empty"},
        {"route": "skip", "reason": "no_issue"},
        {},
    )
    assert out["ok"] is True
    assert out["applied"] is False
    assert not tmp_path.joinpath("issues-receipt.json").exists()
