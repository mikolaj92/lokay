"""Contracts for minimal factory-begin atoms."""

import json
from pathlib import Path


def test_persist_from_config_writes_pass_dir_not_idle(tmp_path, monkeypatch):
    from lokay.proc.persist_factory_begin_state import persist

    state = tmp_path / "state.jsonl"
    state.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        "lokay.proc.seed_prior_catalog.live_issue_to_pr_receipts",
        lambda: [],
    )
    workspace = {"pass_dir": str(tmp_path / "factory-pass-now")}
    Path(workspace["pass_dir"]).mkdir()
    out = persist(
        workspace,
        {
            "live": False,
            "mode": "dry-run",
            "state_path": str(state),
            "repos": ["a/b"],
            "agent": "pi",
        },
        {"repos": ["a/b"]},
        {"route": "up", "offline": False},
    )
    assert out["ok"] is True
    assert out["pass_dir"] == workspace["pass_dir"]
    assert out["idle"] is False
    assert out["planned"][0]["repos"] == ["a/b"]
    assert (Path(workspace["pass_dir"]) / "begin.json").is_file()
    assert (Path(workspace["pass_dir"]) / "working.json").is_file()
    assert (Path(workspace["pass_dir"]) / "tick.json").is_file()


def test_host_probe_stays_up_when_offline_or_empty(monkeypatch):
    from lokay.proc.probe_factory_host import probe

    monkeypatch.delenv("LOKAY_OFFLINE", raising=False)
    assert probe()["route"] == "up"
    monkeypatch.setenv("LOKAY_OFFLINE", "1")
    out = probe()
    assert out["ok"] is True
    assert out["route"] == "up"
    assert out["offline"] is True


def test_live_non_live_config_routes_terminal():
    from lokay.proc.classify_factory_mode import classify

    assert classify({"live": True, "mode": "dry-run"}) == {
        "ok": True,
        "route": "terminal",
        "reason": "mode_not_live",
    }


def test_scope_preserves_catalog_without_override(monkeypatch):
    from lokay.proc.select_factory_scope import select

    monkeypatch.delenv("LOKAY_MILL_REPO", raising=False)
    assert select({"repos": ["a/b", "c/d"]})["repos"] == ["a/b", "c/d"]


def test_terminal_classifier_prefers_preflight_failure():
    from lokay.proc.classify_factory_begin_terminal import classify

    assert classify({"route": "terminal"}, {}, {}, {})["kind"] == "preflight_failed"


def test_begin_receipt_drops_nested_cart():
    from lokay.proc.factory_begin_receipt import begin_receipt

    pad = "x" * 200_000
    out = begin_receipt(
        {
            "ok": True,
            "pass_dir": "/pass",
            "planned": [{"kind": "tick", "repos": ["a/b"]}],
            "stuck_path": "/s",
            "issue_count": 1,
            "stuck": {"issues": {"a/b#1": {"pad": pad}}},
            "fala": {"effector_results": {"harvest": {"stuck": pad}}},
            "terminal": {"harvest_factory_children": {"output": pad}},
            "steps": [{"blob": pad}],
            "begin": {"stuck": {"pad": pad}},
        }
    )
    raw = json.dumps(out)
    assert len(raw) < 10_000
    assert pad not in raw
    assert out["pass_dir"] == "/pass"
    assert "stuck" not in out
    assert "fala" not in out
    assert "terminal" not in out
    assert "begin" not in out


def test_factory_begin_subflow_returns_small_receipt(monkeypatch, tmp_path):
    from lokay.proc.factory_begin_subflow import run

    pad = "y" * 200_000
    monkeypatch.setattr(
        "lokay.proc.factory_begin_subflow.run_path",
        lambda **kwargs: {
            "ok": True,
            "pass_dir": str(tmp_path),
            "planned": [{"repos": ["a/b"]}],
            "stuck_path": str(tmp_path / "stuck.json"),
            "stuck": {"issues": {"a/b#1": {"pad": pad}}},
            "fala": {"cart": pad},
            "terminal": {"harvest_factory_children": {"stuck": pad}},
            "steps": [{"blob": pad}],
            "begin": {"stuck": pad},
        },
    )
    out = run(config_path=None, live=False)
    raw = json.dumps(out)
    assert len(raw) < 10_000
    assert pad not in raw
    assert out["pass_dir"] == str(tmp_path)


def test_persist_begin_seeds_live_occupancy_not_prior_survey(tmp_path, monkeypatch):
    from lokay.proc.persist_factory_begin_state import persist

    state = tmp_path / "state.jsonl"
    state.write_text("", encoding="utf-8")
    prior = tmp_path / "factory-pass-1-aaaaaa"
    prior.mkdir()
    (prior / "working.json").write_text(
        '{"ready_by_repo":{"mikolaj92/reviewkit":[{"number":205}]},"inbox_issues_by_repo":{},"prs_by_repo":{},"occupied_repos":[]}\n',
        encoding="utf-8",
    )
    current = tmp_path / "factory-pass-2-bbbbbb"
    current.mkdir()
    monkeypatch.setattr(
        "lokay.proc.seed_prior_catalog.live_issue_to_pr_receipts",
        lambda: [{"repo": "mikolaj92/Temida", "issue": 1}],
    )
    out = persist(
        {"pass_dir": str(current)},
        {
            "begin": {
                "pass_dir": str(current),
                "stuck_path": str(tmp_path / "stuck.json"),
                "state_path": str(state),
                "planned": [],
            }
        },
        {"working": {"progress": 0, "ready_by_repo": {}, "occupied_repos": []}},
    )
    working = json.loads((current / "working.json").read_text())
    tick = json.loads((current / "tick.json").read_text())
    assert working["ready_by_repo"] == {}
    assert "mikolaj92/Temida" in working["occupied_repos"]
    assert "mikolaj92/Temida" in working["live_issue_to_pr_repos"]
    assert out["ok"] is True
    assert out["pass_dir"] == str(current)
    assert out["idle"] is False
    assert tick["idle"] is False
    assert tick["health"] != "idle"


def test_persist_begin_writes_stuck_from_disk(tmp_path):
    from lokay.proc.persist_factory_begin_state import persist
    from lokay.stuck import save_stuck

    stuck_path = tmp_path / "stuck.json"
    save_stuck(stuck_path, {"issues": {"a/b#1": {"blocked": True}}})
    pass_dir = tmp_path / "pass"
    pass_dir.mkdir()
    out = persist(
        {"pass_dir": str(pass_dir)},
        {"begin": {"pass_dir": str(pass_dir), "stuck_path": str(stuck_path), "planned": []}},
        {"working": {"progress": 0}},
    )
    assert out["ok"] is True
    assert out["pass_dir"] == str(pass_dir)
    assert out["idle"] is False
    begin = json.loads((pass_dir / "begin.json").read_text())
    working = json.loads((pass_dir / "working.json").read_text())
    assert "a/b#1" in begin["stuck"]["issues"]
    assert working["stuck"] == begin["stuck"]


def test_persist_stuck_conducts_path_and_count(tmp_path):
    from lokay.proc.persist_factory_stuck import persist

    path = tmp_path / "stuck.json"
    out = persist(
        {"stuck_path": str(path)},
        {"stuck": {"issues": {"a/b#1": {"blocked": True}}}},
    )
    assert out == {"ok": True, "stuck_path": str(path), "issue_count": 1}
    assert "stuck" not in out
    assert path.is_file()


def test_survey_prs_does_not_receive_begin_blob(monkeypatch):
    from lokay.organ.factory import handle_factory

    captured = {}
    monkeypatch.setattr(
        "lokay.proc.survey_prs_subflow.run",
        lambda **kwargs: captured.update(kwargs) or {"ok": True},
    )
    blob = {
        "pass_dir": "/pass",
        "stuck": {"issues": {"pad": "x" * 50_000}},
        "fala": {"cart": "y" * 50_000},
        "begin": {"stuck": "z" * 50_000},
    }
    ctx = {
        "cfg": None,
        "live": False,
        "repo": "o/r",
        "issue_number": 0,
        "pr_number": 0,
        "repair_mode": False,
        "branch": "",
    }
    out = handle_factory(
        "survey_prs",
        {"config_path": None, "live": False},
        {"factory_begin": blob},
        ctx,
    )
    assert out == {"ok": True}
    assert captured == {"pass_dir": "/pass", "config_path": None, "live": False}
    assert "stuck" not in captured
    assert "fala" not in captured
    assert "begin" not in captured
