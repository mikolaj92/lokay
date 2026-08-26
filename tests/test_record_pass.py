"""Leaf record_pass: small receipt (new_pr / merge / none); leftover overflow skips."""

from pathlib import Path

from lokay.pass_history import read_pass_history
from lokay.pass_receipt import read_pass_receipt
from lokay.passkit import io as pass_io
from lokay.proc.record_pass import classify_outcome, leftover_overflowed, run_record_pass


def _begin(tmp_path: Path, **extra) -> Path:
    pass_dir = tmp_path / "pass"
    pass_dir.mkdir()
    pass_io.write_json(
        pass_io.begin_path(pass_dir),
        {
            "merge_enabled": True,
            "require_checks": False,
            "require_llm_review": True,
            "max_issue_to_pr_per_pass": 1,
            "config_path": str(tmp_path / "config.yaml"),
            "state_path": str(tmp_path / "state.jsonl"),
            **extra,
        },
    )
    return pass_dir


def test_classify_merge_wins_over_new_pr() -> None:
    assert (
        classify_outcome(
            prs={"result": {"merged": True}},
            issues={"result": {"launched": "started"}},
        )
        == "merge"
    )


def test_classify_new_pr_from_issues_launch() -> None:
    assert classify_outcome(issues={"result": {"launched": "started"}}) == "new_pr"


def test_classify_none_when_children_skip() -> None:
    assert (
        classify_outcome(
            prs={"result": {"route": "none"}},
            issues={"result": {"route": "skip", "launched": None}},
        )
        == "none"
    )


def test_leftover_overflow_is_skip_not_fail(tmp_path: Path) -> None:
    leftover = {"ok": True, "route": "skip", "skipped": True, "reason": "leftover_overflow"}
    assert leftover_overflowed(leftover) is True
    out = run_record_pass(pass_dir=str(_begin(tmp_path)), leftover=leftover)
    assert out["ok"] is True
    assert out["outcome"] == "none"
    assert out["result"]["leftover_overflow"] is True
    assert out["result"]["idle"] is False


def test_leftover_overflow_does_not_fail_when_tick_missing(tmp_path: Path) -> None:
    pass_dir = _begin(tmp_path)
    leftover = {
        "ok": False,
        "error": "leftover closeout catalog exceeds authored slots",
        "reason": "leftover_overflow",
        "candidates": [{"repo": f"o/r{i}"} for i in range(40)],
    }
    out = run_record_pass(pass_dir=str(pass_dir), leftover=leftover)
    assert out["ok"] is True
    assert out["outcome"] == "none"
    receipt = read_pass_receipt(state_path=tmp_path / "state.jsonl")
    assert receipt is not None
    assert receipt["outcome"] == "none"
    assert receipt["leftover_overflow"] is True
    assert "candidates" not in receipt
    assert "by_repo" not in receipt.get("remaining", {})


def test_writes_new_pr_receipt(tmp_path: Path) -> None:
    pass_dir = _begin(tmp_path)
    pass_io.write_json(pass_io.working_path(pass_dir), {"issue_to_pr_started": 1})
    out = run_record_pass(
        pass_dir=str(pass_dir),
        issues={"result": {"route": "do", "launched": "started"}},
    )
    assert out["ok"] is True
    assert out["outcome"] == "new_pr"
    receipt = read_pass_receipt(state_path=tmp_path / "state.jsonl")
    assert receipt is not None
    assert receipt["outcome"] == "new_pr"
    assert receipt["progress"] == 1
    assert read_pass_history(state_path=tmp_path / "state.jsonl")[0]["outcome"] == "new_pr"


def test_writes_merge_receipt(tmp_path: Path) -> None:
    pass_dir = _begin(tmp_path)
    out = run_record_pass(
        pass_dir=str(pass_dir),
        prs={"result": {"route": "pr", "triage": {"merged": True}}},
    )
    assert out["ok"] is True
    assert out["outcome"] == "merge"
    receipt = read_pass_receipt(state_path=tmp_path / "state.jsonl")
    assert receipt is not None
    assert receipt["outcome"] == "merge"


def test_leftover_overflow_still_records_merge(tmp_path: Path) -> None:
    pass_dir = _begin(tmp_path)
    out = run_record_pass(
        pass_dir=str(pass_dir),
        prs={"result": {"merged": True}},
        leftover={"reason": "leftover_overflow", "count": 40},
    )
    assert out["ok"] is True
    assert out["outcome"] == "merge"
    assert out["result"]["leftover_overflow"] is True


def test_writes_none_receipt_when_tick_missing(tmp_path: Path) -> None:
    out = run_record_pass(pass_dir=str(_begin(tmp_path)))
    assert out["ok"] is True
    assert out["outcome"] == "none"
    assert out["result"]["health"] == "idle"
    receipt = read_pass_receipt(state_path=tmp_path / "state.jsonl")
    assert receipt is not None
    assert receipt["outcome"] == "none"
