"""Merged closing PR closeout removes readiness before another issue-to-PR run."""

from __future__ import annotations

import os
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

import lokay.compose.issue_to_pr as issue_to_pr
from lokay.compose import mill as mill_mod
from lokay.proc import closeout


def test_open_issue_with_merged_fixes_pr_removes_ready_labels(monkeypatch):
    monkeypatch.setattr(
        closeout,
        "load_cfg",
        lambda _args: SimpleNamespace(config_path=None),
    )
    monkeypatch.setattr(closeout, "mutations_allowed", lambda **_kwargs: True)
    monkeypatch.setattr(
        closeout,
        "find_pr_fixing_issue",
        lambda _runner, _repo, _issue, live, merged_only: {
            "number": 41,
            "state": "closed",
            "merged_at": "2026-08-20T10:00:00Z",
            "body": "Fixes #7",
        },
    )
    parked: list[list[str]] = []

    def run_proc(_main, argv):
        parked.append(argv)
        return {"ok": True, "removed": True}

    monkeypatch.setattr(closeout, "run_proc", run_proc)

    out = closeout.run_closeout(repo="owner/repo", issue=7, config_path=None, live=True)

    assert out["delivered"] is True
    assert out["labels_removed"] is True
    assert out["pr"] == 41
    assert parked == [["--repo", "owner/repo", "--issue", "7", "--live"]]


def test_existing_delivery_closeout_is_an_explicit_fala_edge():
    from lokay.graph_run import describe_package

    path = next(p for p in describe_package()["paths"] if p["id"] == "issue_to_pr")
    by_id = {node["id"]: node for node in path["nodes"]}
    assert by_id["close_existing_delivery"]["when"] == {
        "upstream": "resolve_existing_delivery",
        "path": "route",
        "equals": "closeout",
    }
    assert by_id["issue_to_pr_subflow"]["when"]["equals"] == "deliver"


def test_leftover_closed_ready_parks_without_searching_prs(monkeypatch):
    monkeypatch.setattr(
        closeout,
        "load_cfg",
        lambda _args: SimpleNamespace(
            repos=[SimpleNamespace(name="mikolaj92/lokay")],
            ready_label="ai:ready",
        ),
    )
    monkeypatch.setattr(closeout, "mutations_allowed", lambda **_kwargs: True)
    monkeypatch.setattr(closeout, "runner", lambda _cfg: object())
    monkeypatch.setattr(closeout, "closed_ready_numbers", lambda *_a, **_k: [429])

    def boom(*_a, **_k):
        raise AssertionError("leftover closeout must not paginate mill PRs")

    monkeypatch.setattr(closeout, "find_pr_fixing_issue", boom)
    parked: list[list[str]] = []

    def run_proc(_main, argv):
        parked.append(argv)
        return {"ok": True, "removed": True}

    monkeypatch.setattr(closeout, "run_proc", run_proc)
    out = closeout.run_closeout_leftover(config_path=None, live=True)
    assert out["labels_removed"] is True
    assert out["closed_out"] == [{"repo": "mikolaj92/lokay", "issue": 429}]
    assert parked == [["--repo", "mikolaj92/lokay", "--issue", "429", "--live"]]


def test_leftover_skips_github_when_recent_empty_stamp(monkeypatch, tmp_path):
    stamp = tmp_path / "leftover-closeout.stamp"
    stamp.write_text("1", encoding="utf-8")
    monkeypatch.setattr(
        closeout,
        "load_cfg",
        lambda _args: SimpleNamespace(
            repos=[SimpleNamespace(name="mikolaj92/lokay")],
            ready_label="ai:ready",
            state_path=tmp_path / "state.jsonl",
        ),
    )
    monkeypatch.setattr(closeout, "mutations_allowed", lambda **_kwargs: True)

    def boom(*_a, **_k):
        raise AssertionError("recent empty leftover must not list GitHub")

    monkeypatch.setattr(closeout, "closed_ready_numbers", boom)
    monkeypatch.setattr(closeout, "runner", lambda _cfg: object())
    out = closeout.run_closeout_leftover(config_path=None, live=True)
    assert out["skipped"] is True
    assert out["reason"] == "recent_empty"
    assert out["labels_removed"] is False
    assert out["closed_out"] == []


def test_fresh_leftover_skip_does_not_require_healthy(monkeypatch, tmp_path):
    """Fresh leftover skip does not require healthy. Hosted leftover parks still do."""
    stamp = tmp_path / "leftover-closeout.stamp"
    stamp.write_text("1", encoding="utf-8")
    monkeypatch.setattr(
        closeout,
        "load_cfg",
        lambda _args: SimpleNamespace(
            repos=[SimpleNamespace(name="mikolaj92/lokay")],
            ready_label="ai:ready",
            state_path=tmp_path / "state.jsonl",
        ),
    )

    def boom(**_kwargs):
        raise AssertionError("fresh leftover skip does not require healthy")

    monkeypatch.setattr(closeout, "mutations_allowed", boom)
    monkeypatch.setattr(
        closeout,
        "closed_ready_numbers",
        lambda *_a, **_k: (_ for _ in ()).throw(
            AssertionError("recent empty leftover must not list GitHub")
        ),
    )
    out = closeout.run_closeout_leftover(config_path=None, live=True)
    assert out["skipped"] is True
    assert out["reason"] == "recent_empty"
    src = Path(__file__).resolve().parents[1] / "src" / "lokay" / "proc" / "closeout.py"
    assert "Fresh leftover skip does not require healthy." in src.read_text(
        encoding="utf-8"
    )


def test_fresh_leftover_closeout_skip_is_not_applied(monkeypatch, tmp_path):
    """Fresh leftover-closeout skip is not applied."""
    stamp = tmp_path / "leftover-closeout.stamp"
    stamp.write_text("1", encoding="utf-8")
    monkeypatch.setattr(
        closeout,
        "load_cfg",
        lambda _args: SimpleNamespace(
            repos=[SimpleNamespace(name="mikolaj92/lokay")],
            ready_label="ai:ready",
            state_path=tmp_path / "state.jsonl",
        ),
    )

    def boom(**_kwargs):
        raise AssertionError("fresh leftover skip does not require healthy")

    monkeypatch.setattr(closeout, "mutations_allowed", boom)
    monkeypatch.setattr(
        closeout,
        "closed_ready_numbers",
        lambda *_a, **_k: (_ for _ in ()).throw(
            AssertionError("recent empty leftover must not list GitHub")
        ),
    )
    out = closeout.run_closeout_leftover(config_path=None, live=True)
    assert out["skipped"] is True
    assert out["reason"] == "recent_empty"
    assert out["applied"] is False
    src = Path(__file__).resolve().parents[1] / "src" / "lokay" / "proc" / "closeout.py"
    assert "Fresh leftover-closeout skip is not applied." in src.read_text(
        encoding="utf-8"
    )


def test_leftover_closeout_skip_reports_planned_not_live(monkeypatch, tmp_path):
    """Leftover-closeout skip reports planned=not live."""
    stamp = tmp_path / "leftover-closeout.stamp"
    stamp.write_text("1", encoding="utf-8")
    monkeypatch.setattr(
        closeout,
        "load_cfg",
        lambda _args: SimpleNamespace(
            repos=[SimpleNamespace(name="mikolaj92/lokay")],
            ready_label="ai:ready",
            state_path=tmp_path / "state.jsonl",
        ),
    )

    def boom(**_kwargs):
        raise AssertionError("fresh leftover skip does not require healthy")

    monkeypatch.setattr(closeout, "mutations_allowed", boom)
    monkeypatch.setattr(
        closeout,
        "closed_ready_numbers",
        lambda *_a, **_k: (_ for _ in ()).throw(
            AssertionError("recent empty leftover must not list GitHub")
        ),
    )
    live = closeout.run_closeout_leftover(config_path=None, live=True)
    assert live["skipped"] is True
    assert live["reason"] == "recent_empty"
    assert live["applied"] is False
    assert live["planned"] is False
    dry = closeout.run_closeout_leftover(config_path=None, live=False)
    assert dry["skipped"] is True
    assert dry["planned"] is True
    src = Path(__file__).resolve().parents[1] / "src" / "lokay" / "proc" / "closeout.py"
    assert "Leftover-closeout skip reports planned=not live." in src.read_text(
        encoding="utf-8"
    )


def test_leftover_closeout_skip_reports_probe_failed(monkeypatch, tmp_path):
    """Leftover-closeout skip reports probe_failed."""
    stamp = tmp_path / "leftover-closeout.stamp"
    stamp.write_text("1", encoding="utf-8")
    monkeypatch.setattr(
        closeout,
        "load_cfg",
        lambda _args: SimpleNamespace(
            repos=[SimpleNamespace(name="mikolaj92/lokay")],
            ready_label="ai:ready",
            state_path=tmp_path / "state.jsonl",
        ),
    )
    monkeypatch.setattr(
        closeout,
        "closed_ready_numbers",
        lambda *_a, **_k: (_ for _ in ()).throw(
            AssertionError("recent empty leftover must not list GitHub")
        ),
    )
    out = closeout.run_closeout_leftover(config_path=None, live=True)
    assert out["skipped"] is True
    assert out["probe_failed"] is False
    assert out["applied"] is False
    src = Path(__file__).resolve().parents[1] / "src" / "lokay" / "proc" / "closeout.py"
    assert "Leftover-closeout skip reports probe_failed." in src.read_text(
        encoding="utf-8"
    )


def test_unhealthy_leftover_closeout_still_lists_github(monkeypatch, tmp_path):
    """Unhealthy leftover-closeout still lists GitHub. Hosted leftover parks still do."""
    stamp = tmp_path / "leftover-closeout.stamp"
    stamp.write_text("1", encoding="utf-8")
    old = time.time() - closeout.LEFTOVER_TTL_SECONDS - 1
    os.utime(stamp, (old, old))
    listed: list[bool] = []
    parked_live: list[bool] = []
    monkeypatch.setattr(
        closeout,
        "load_cfg",
        lambda _args: SimpleNamespace(
            repos=[SimpleNamespace(name="mikolaj92/lokay")],
            ready_label="ai:ready",
            state_path=tmp_path / "state.jsonl",
        ),
    )
    monkeypatch.setattr(closeout, "mutations_allowed", lambda **_kwargs: False)
    monkeypatch.setattr(closeout, "runner", lambda _cfg: object())

    def fake_closed(_runner, repo, label, *, live):
        listed.append(bool(live))
        return [429]

    def fake_park(*, repo, issue, allowed, config_path=None):
        parked_live.append(bool(allowed))
        return {"ok": True, "planned": True, "removed": False}

    monkeypatch.setattr(closeout, "closed_ready_numbers", fake_closed)
    monkeypatch.setattr(closeout, "_park_ready", fake_park)
    out = closeout.run_closeout_leftover(config_path=None, live=True)
    assert listed == [True, True]
    assert parked_live == [False]
    assert out["leftover_closed"] == 0
    assert out["labels_removed"] is False
    assert stamp.is_file()
    assert stamp.stat().st_mtime == old
    src = Path(__file__).resolve().parents[1] / "src" / "lokay" / "proc" / "closeout.py"
    assert "Unhealthy leftover-closeout still lists GitHub." in src.read_text(
        encoding="utf-8"
    )


def test_unhealthy_leftover_closeout_parks_are_planned(monkeypatch, tmp_path):
    """Unhealthy leftover-closeout parks are planned."""
    stamp = tmp_path / "leftover-closeout.stamp"
    stamp.write_text("1", encoding="utf-8")
    old = time.time() - closeout.LEFTOVER_TTL_SECONDS - 1
    os.utime(stamp, (old, old))
    monkeypatch.setattr(
        closeout,
        "load_cfg",
        lambda _args: SimpleNamespace(
            repos=[SimpleNamespace(name="mikolaj92/lokay")],
            ready_label="ai:ready",
            state_path=tmp_path / "state.jsonl",
        ),
    )
    monkeypatch.setattr(closeout, "mutations_allowed", lambda **_kwargs: False)
    monkeypatch.setattr(closeout, "runner", lambda _cfg: object())
    monkeypatch.setattr(
        closeout,
        "closed_ready_numbers",
        lambda *_a, **_k: [429],
    )
    monkeypatch.setattr(
        closeout,
        "_park_ready",
        lambda **_k: {"ok": True, "planned": True, "removed": False},
    )
    out = closeout.run_closeout_leftover(config_path=None, live=True)
    assert out["leftover_closed"] == 0
    assert out["labels_removed"] is False
    assert out["planned"] is True
    assert out["closed_out"] == [
        {"repo": "mikolaj92/lokay", "issue": 429, "planned": True}
    ]
    assert stamp.is_file()
    assert stamp.stat().st_mtime == old
    src = Path(__file__).resolve().parents[1] / "src" / "lokay" / "proc" / "closeout.py"
    assert "Unhealthy leftover-closeout parks are planned." in src.read_text(
        encoding="utf-8"
    )


def test_hosted_leftover_closeout_reports_applied(monkeypatch, tmp_path):
    """Hosted leftover-closeout reports applied."""
    stamp = tmp_path / "leftover-closeout.stamp"
    stamp.write_text("1", encoding="utf-8")
    old = time.time() - closeout.LEFTOVER_TTL_SECONDS - 1
    os.utime(stamp, (old, old))
    monkeypatch.setattr(
        closeout,
        "load_cfg",
        lambda _args: SimpleNamespace(
            repos=[SimpleNamespace(name="mikolaj92/lokay")],
            ready_label="ai:ready",
            state_path=tmp_path / "state.jsonl",
        ),
    )
    monkeypatch.setattr(closeout, "runner", lambda _cfg: object())
    monkeypatch.setattr(
        closeout,
        "closed_ready_numbers",
        lambda *_a, **_k: [429],
    )
    monkeypatch.setattr(
        closeout,
        "_park_ready",
        lambda **_k: {"ok": True, "planned": True, "removed": False},
    )
    monkeypatch.setattr(closeout, "mutations_allowed", lambda **_kwargs: False)
    unhealthy = closeout.run_closeout_leftover(config_path=None, live=True)
    assert unhealthy["applied"] is False
    assert unhealthy["planned"] is True
    monkeypatch.setattr(closeout, "mutations_allowed", lambda **_kwargs: True)
    monkeypatch.setattr(
        closeout,
        "_park_ready",
        lambda **_k: {"ok": True, "removed": True},
    )
    healthy = closeout.run_closeout_leftover(config_path=None, live=True)
    assert healthy["applied"] is True
    assert healthy["labels_removed"] is True
    src = Path(__file__).resolve().parents[1] / "src" / "lokay" / "proc" / "closeout.py"
    assert "Hosted leftover-closeout reports applied." in src.read_text(
        encoding="utf-8"
    )


def test_pytest_does_not_skip_leftover_github_lists_using_the_mill_stamp(
    monkeypatch, tmp_path
):
    mill = tmp_path / ".lokay"
    mill.mkdir()
    stamp = mill / "leftover-closeout.stamp"
    stamp.write_text("1", encoding="utf-8")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv(
        "PYTEST_CURRENT_TEST",
        "test_pytest_does_not_skip_leftover_github_lists_using_the_mill_stamp",
    )
    assert closeout.leftover_recently_empty(stamp) is False
    listed: list[str] = []
    monkeypatch.setattr(
        closeout,
        "load_cfg",
        lambda _args: SimpleNamespace(
            repos=[SimpleNamespace(name="mikolaj92/lokay")],
            ready_label="ai:ready",
            state_path=mill / "state.jsonl",
        ),
    )
    monkeypatch.setattr(closeout, "mutations_allowed", lambda **_kwargs: True)
    monkeypatch.setattr(
        closeout, "closed_ready_numbers", lambda *_a, **_k: listed.append("gh") or []
    )
    monkeypatch.setattr(closeout, "runner", lambda _cfg: object())
    out = closeout.run_closeout_leftover(config_path=None, live=True)
    assert out.get("skipped") is not True
    assert listed == ["gh", "gh"]
    hermetic = tmp_path / "leftover-closeout.stamp"
    hermetic.write_text("1", encoding="utf-8")
    assert closeout.leftover_recently_empty(hermetic) is True
    src = Path(__file__).resolve().parents[1] / "src" / "lokay" / "proc" / "closeout.py"
    assert (
        "Pytest must not skip leftover GitHub lists using the mill stamp."
        in src.read_text(encoding="utf-8")
    )


def test_leftover_probes_when_empty_stamp_expired(monkeypatch, tmp_path):
    stamp = tmp_path / "leftover-closeout.stamp"
    stamp.write_text("1", encoding="utf-8")
    old = time.time() - closeout.LEFTOVER_TTL_SECONDS - 1
    os.utime(stamp, (old, old))
    monkeypatch.setattr(
        closeout,
        "load_cfg",
        lambda _args: SimpleNamespace(
            repos=[SimpleNamespace(name="mikolaj92/lokay")],
            ready_label="ai:ready",
            state_path=tmp_path / "state.jsonl",
        ),
    )
    monkeypatch.setattr(closeout, "mutations_allowed", lambda **_kwargs: True)
    monkeypatch.setattr(closeout, "closed_ready_numbers", lambda *_a, **_k: [])
    monkeypatch.setattr(closeout, "runner", lambda _cfg: object())
    out = closeout.run_closeout_leftover(config_path=None, live=True)
    assert out.get("skipped") is not True
    assert out["labels_removed"] is False
    assert stamp.is_file()
    assert stamp.stat().st_mtime >= old + closeout.LEFTOVER_TTL_SECONDS


def test_leftover_empty_probe_writes_stamp(monkeypatch, tmp_path):
    stamp = tmp_path / "leftover-closeout.stamp"
    monkeypatch.setattr(
        closeout,
        "load_cfg",
        lambda _args: SimpleNamespace(
            repos=[SimpleNamespace(name="mikolaj92/lokay")],
            ready_label="ai:ready",
            state_path=tmp_path / "state.jsonl",
        ),
    )
    monkeypatch.setattr(closeout, "mutations_allowed", lambda **_kwargs: True)
    monkeypatch.setattr(closeout, "closed_ready_numbers", lambda *_a, **_k: [])
    monkeypatch.setattr(closeout, "runner", lambda _cfg: object())
    out = closeout.run_closeout_leftover(config_path=None, live=True)
    assert out["labels_removed"] is False
    assert out["applied"] is False
    assert stamp.is_file()


def test_empty_leftover_closeout_host_is_not_applied(monkeypatch, tmp_path):
    """Empty leftover-closeout host is not applied."""
    stamp = tmp_path / "leftover-closeout.stamp"
    monkeypatch.setattr(
        closeout,
        "load_cfg",
        lambda _args: SimpleNamespace(
            repos=[SimpleNamespace(name="mikolaj92/lokay")],
            ready_label="ai:ready",
            state_path=tmp_path / "state.jsonl",
        ),
    )
    monkeypatch.setattr(closeout, "mutations_allowed", lambda **_kwargs: True)
    monkeypatch.setattr(closeout, "closed_ready_numbers", lambda *_a, **_k: [])
    monkeypatch.setattr(closeout, "runner", lambda _cfg: object())
    monkeypatch.setattr(
        closeout,
        "_park_ready",
        lambda **_k: (_ for _ in ()).throw(
            AssertionError("empty leftover-closeout host must not park")
        ),
    )
    out = closeout.run_closeout_leftover(config_path=None, live=True)
    assert out["applied"] is False
    assert out["leftover_closed"] == 0
    src = Path(__file__).resolve().parents[1] / "src" / "lokay" / "proc" / "closeout.py"
    assert "Empty leftover-closeout host is not applied." in src.read_text(
        encoding="utf-8"
    )


def test_leftover_closeout_rate_limit_does_not_stamp_empty(monkeypatch, tmp_path):
    """Leftover-closeout rate limit does not stamp empty."""
    stamp = tmp_path / "leftover-closeout.stamp"
    stamp.write_text("1", encoding="utf-8")
    old = time.time() - closeout.LEFTOVER_TTL_SECONDS - 1
    os.utime(stamp, (old, old))
    monkeypatch.setattr(
        closeout,
        "load_cfg",
        lambda _args: SimpleNamespace(
            repos=[SimpleNamespace(name="mikolaj92/lokay")],
            ready_label="ai:ready",
            state_path=tmp_path / "state.jsonl",
        ),
    )
    monkeypatch.setattr(closeout, "mutations_allowed", lambda **_kwargs: True)
    monkeypatch.setattr(closeout, "runner", lambda _cfg: object())
    monkeypatch.setattr(
        closeout,
        "closed_ready_numbers",
        lambda *_a, **_k: (_ for _ in ()).throw(
            RuntimeError("HTTP 429: API rate limit exceeded")
        ),
    )
    monkeypatch.setattr(
        closeout,
        "_park_ready",
        lambda **_k: (_ for _ in ()).throw(
            AssertionError("failed probe must not park leftovers")
        ),
    )
    out = closeout.run_closeout_leftover(config_path=None, live=True)
    assert out["probe_failed"] is True
    assert out["applied"] is False
    assert out["leftover_closed"] == 0
    assert stamp.stat().st_mtime == old
    src = Path(__file__).resolve().parents[1] / "src" / "lokay" / "proc" / "closeout.py"
    assert "Leftover-closeout rate limit does not stamp empty." in src.read_text(
        encoding="utf-8"
    )


def test_leftover_park_clears_empty_stamp(monkeypatch, tmp_path):
    stamp = tmp_path / "leftover-closeout.stamp"
    stamp.write_text("1", encoding="utf-8")
    old = time.time() - closeout.LEFTOVER_TTL_SECONDS - 1
    os.utime(stamp, (old, old))
    monkeypatch.setattr(
        closeout,
        "load_cfg",
        lambda _args: SimpleNamespace(
            repos=[SimpleNamespace(name="mikolaj92/lokay")],
            ready_label="ai:ready",
            state_path=tmp_path / "state.jsonl",
        ),
    )
    monkeypatch.setattr(closeout, "mutations_allowed", lambda **_kwargs: True)
    monkeypatch.setattr(closeout, "closed_ready_numbers", lambda *_a, **_k: [429])
    monkeypatch.setattr(closeout, "runner", lambda _cfg: object())
    monkeypatch.setattr(
        closeout, "run_proc", lambda *_a, **_k: {"ok": True, "removed": True}
    )
    out = closeout.run_closeout_leftover(config_path=None, live=True)
    assert out["labels_removed"] is True
    assert out["closed_out"] == [{"repo": "mikolaj92/lokay", "issue": 429}]
    assert not stamp.exists()


def test_closed_ready_numbers_refuses_truncated_list():
    cap = closeout.survey_list_cap()

    class FullPageRunner:
        def run_checked(self, spec, *, live):
            assert live is True
            assert spec.argv[-1] == str(cap)
            return SimpleNamespace(
                stdout="["
                + ",".join('{"number":1,"state":"CLOSED"}' for _ in range(cap))
                + "]"
            )

    with pytest.raises(RuntimeError, match="hit the 1000 newest-first cap"):
        closeout.closed_ready_numbers(
            FullPageRunner(), "mikolaj92/lokay", "work:ready", live=True
        )


def test_closed_ready_numbers_pin_refuses_silent_truncation():
    source = (Path(closeout.__file__)).read_text(encoding="utf-8")
    assert "Leftover-closeout refuses a silently truncated CLOSED issue list." in source


def test_leftover_closed_ready_clears_inflight_signal():
    from lokay.proc.apply_product_leftover import apply
    from lokay.proc.record_product_pass import record
    from lokay.proc.classify_product_pass import classify as classify_pass
    from lokay.proc.classify_product_plateau import classify as classify_plateau
    from lokay.proc.decide_product_pass_stop import decide
    from lokay.proc.finalize_product_pass import finalize

    def evaluate(prepared, selected, tick, leftover, previous):
        applied = apply(tick, leftover)
        recorded = record(selected, applied, previous)
        classified = classify_pass(prepared, recorded)
        plateau = classify_plateau(classified)
        decided = decide(prepared, plateau)
        return finalize(prepared, decided)

    prepared = {"mode": "live", "live": True, "budget": 1}
    tick = {
        "ok": True,
        "health": "progress",
        "progress": 0,
        "remaining": {"ready": 1, "issue_to_pr_started": 1},
    }
    out = evaluate(
        prepared, {"slot": 1}, tick, {"labels_removed": True, "leftover_closed": 1}, {}
    )
    assert out["payload"]["remaining"]["issue_to_pr_started"] == 0
    assert out["payload"]["progress"] == 1
