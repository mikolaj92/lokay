"""pr_repair admission + mid-flight MERGED guard (#1073)."""

from __future__ import annotations

from pathlib import Path

import pytest

from lokay.compose import pr_repair as compose_mod
from lokay.organ.common import _merged_pr_payload, _pr_already_merged
from lokay.proc import pr_repair_receipts as receipts
from lokay.proc.run_parent_pr_repair_subflow import run as run_parent
from lokay.proc.summarize_pr_repair import summarize


def test_merged_payload_refuses() -> None:
    out = _merged_pr_payload(
        {"route": "merged", "merged": True, "state": "MERGED", "repo": "o/r", "pr": 1072}
    )
    assert out is not None
    assert out["ok"] is False
    assert out["reason"] == "pr_already_merged"


def test_open_payload_allows() -> None:
    assert _merged_pr_payload({"route": "open", "merged": False, "state": "OPEN"}) is None


def test_mid_flight_uses_admit_conduction() -> None:
    refused = _pr_already_merged(
        {"admit_pr_repair": {"route": "skip", "reason": "pr_already_merged", "merged": True, "state": "MERGED", "repo": "o/r", "pr": 9}},
        live=["--live"],
        repo="o/r",
        pr_number=9,
    )
    assert refused is not None
    assert refused["reason"] == "pr_already_merged"


def test_summarize_admit_skip() -> None:
    out = summarize(
        final={},
        push={},
        repo="o/r",
        pr=1072,
        branch="ai/fix/1071-x",
        admit={"route": "skip", "reason": "pr_already_merged"},
    )
    assert out["ok"] is True
    assert out["result"]["skipped"] is True
    assert out["result"]["terminal"] == "pr_already_merged"


def test_compose_skips_merged_without_run_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[object] = []

    def boom(**_kwargs: object) -> dict:
        calls.append(1)
        raise AssertionError("run_path must not start for MERGED")

    monkeypatch.setattr(compose_mod, "run_path", boom)
    monkeypatch.setattr(
        compose_mod,
        "admit_live",
        lambda **_k: {
            "ok": True,
            "route": "skip",
            "reason": "pr_already_merged",
            "merged": True,
            "state": "MERGED",
            "repo": "mikolaj92/lokay",
            "pr": 1072,
        },
    )
    monkeypatch.setattr(
        compose_mod,
        "load_config",
        lambda _p=None: type(
            "C",
            (),
            {"mode": "live", "state_path": tmp_path / "state.jsonl"},
        )(),
    )
    out = compose_mod.compose_pr_repair(
        config_path=str(tmp_path / "c.yaml"),
        repo="mikolaj92/lokay",
        pr_number=1072,
        branch="ai/fix/1071-x",
        live=True,
    )
    assert calls == []
    assert out["skipped"] is True
    assert out["reason"] == "pr_already_merged"
    assert out["result"]["terminal"] == "pr_already_merged"


def test_parent_skip_does_not_stamp_budget(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "lokay.proc.run_parent_pr_repair_subflow.compose_pr_repair",
        lambda **_k: {
            "ok": True,
            "skipped": True,
            "reason": "pr_already_merged",
            "result": {
                "skipped": True,
                "terminal": "pr_already_merged",
                "reason": "pr_already_merged",
                "head_sha": "",
            },
        },
    )
    monkeypatch.setattr(
        receipts,
        "resolve_budget",
        lambda _c=None: 1,
    )
    monkeypatch.setattr(receipts, "resolve_state_dir", lambda _c=None: tmp_path)
    stamped: list[object] = []

    def stamp(*_a, **_k):
        stamped.append(1)
        raise AssertionError("must not stamp on MERGED skip")

    monkeypatch.setattr(receipts, "stamp", stamp)
    out = run_parent(
        {
            "repo": "o/r",
            "pr": 1072,
            "branch": "ai/fix/1071-x",
            "review": {},
        },
        config_path=None,
        live=True,
    )
    assert stamped == []
    assert out["route"] == "skip"
    assert out["reason"] == "pr_already_merged"
    assert out["attempts"] == 0
