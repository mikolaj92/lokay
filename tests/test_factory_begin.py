"""Contracts for minimal factory-begin atoms."""

import json
from pathlib import Path


def test_composed_begin_atoms_write_pass_dir_not_idle(tmp_path, monkeypatch):
    from lokay.proc.attach_factory_stuck import attach
    from lokay.proc.build_factory_begin_state import build as build_begin
    from lokay.proc.build_factory_working_state import build as build_working
    from lokay.proc.persist_factory_begin_state import persist as persist_begin
    from lokay.proc.persist_factory_tick import persist as persist_tick
    from lokay.proc.persist_factory_working_state import persist as persist_working
    from lokay.proc.seed_factory_occupancy import run as seed_occupancy

    state = tmp_path / "state.jsonl"
    state.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        "lokay.proc.seed_prior_catalog.live_issue_to_pr_receipts",
        lambda: [],
    )
    workspace = {"pass_dir": str(tmp_path / "factory-pass-now")}
    Path(workspace["pass_dir"]).mkdir()
    config = {
        "live": False,
        "mode": "dry-run",
        "state_path": str(state),
        "repos": ["a/b"],
        "agent": "pi",
    }
    scope = {"repos": ["a/b"]}
    ledger = {"stuck_path": str(tmp_path / "stuck.json"), "issue_count": 0}
    begin = build_begin(config, scope, ledger, workspace)
    working = seed_occupancy(build_working(ledger))
    attached = attach(begin, working, ledger)
    assert persist_begin(workspace, attached)["pass_dir"] == workspace["pass_dir"]
    assert persist_working(workspace, attached)["pass_dir"] == workspace["pass_dir"]
    out = persist_tick(workspace, attached, {"offline": False}, ledger)
    assert out["ok"] is True
    assert out["pass_dir"] == workspace["pass_dir"]
    assert out["idle"] is False
    assert out["planned"][0]["repos"] == ["a/b"]
    assert (Path(workspace["pass_dir"]) / "begin.json").is_file()
    assert (Path(workspace["pass_dir"]) / "working.json").is_file()
    assert (Path(workspace["pass_dir"]) / "tick.json").is_file()


def test_persist_begin_writes_only_begin_json(tmp_path):
    from lokay.proc.persist_factory_begin_state import persist
    import inspect

    source = inspect.getsource(persist)
    assert "build_begin" not in source
    assert "build_working" not in source
    assert "seed(" not in source
    assert "tick_path" not in source
    workspace = {"pass_dir": str(tmp_path)}
    out = persist(workspace, {"begin": {"pass_dir": str(tmp_path), "planned": []}})
    assert out == {"ok": True, "pass_dir": str(tmp_path)}
    assert (tmp_path / "begin.json").is_file()
    assert not (tmp_path / "working.json").exists()
    assert not (tmp_path / "tick.json").exists()


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


def test_begin_receipt_lifts_pass_dir_from_persist_tick(tmp_path):
    """Nested Fala keeps pass_dir on persist_factory_tick; receipt must keep it."""
    from lokay.proc.factory_begin_receipt import begin_receipt

    pad = "z" * 50_000
    pass_dir = str(tmp_path / "factory-pass-now")
    out = begin_receipt(
        {
            "ok": True,
            "live": True,
            "atom": "factory_begin",
            "fala": {"cart": pad},
            "terminal": {
                "persist_factory_tick": {
                    "step": "persist_factory_tick",
                    "status": "succeeded",
                    "ok": True,
                    "pass_dir": pass_dir,
                    "stuck_path": str(tmp_path / "stuck.json"),
                    "planned": [{"kind": "tick", "repos": ["a/b"]}],
                    "live": True,
                    "mode": "live",
                    "offline": False,
                    "issue_count": 0,
                    "idle": False,
                },
                "merge_leftover_remaining": {
                    "step": "merge_leftover_remaining",
                    "status": "succeeded",
                    "ok": True,
                    "pass_dir": pass_dir,
                    "written": False,
                    "route": "keep",
                },
            },
            "steps": [{"blob": pad}],
            "stuck": {"issues": {"pad": pad}},
        }
    )
    raw = json.dumps(out)
    assert pad not in raw
    assert "fala" not in out
    assert "terminal" not in out
    assert "steps" not in out
    assert "stuck" not in out
    assert "atom" not in out
    assert out["ok"] is True
    assert out["pass_dir"] == pass_dir
    assert out["stuck_path"] == str(tmp_path / "stuck.json")
    assert out["planned"] == [{"kind": "tick", "repos": ["a/b"]}]
    assert out["live"] is True
    assert out["idle"] is False


def test_begin_receipt_prefers_top_level_over_nested(tmp_path):
    from lokay.proc.factory_begin_receipt import begin_receipt

    out = begin_receipt(
        {
            "ok": True,
            "pass_dir": str(tmp_path / "top"),
            "terminal": {
                "persist_factory_tick": {
                    "ok": True,
                    "pass_dir": str(tmp_path / "nested"),
                }
            },
        }
    )
    assert out["pass_dir"] == str(tmp_path / "top")


def test_begin_receipt_lifts_from_merge_leftover_when_tick_missing(tmp_path):
    from lokay.proc.factory_begin_receipt import begin_receipt

    pass_dir = str(tmp_path / "from-merge")
    out = begin_receipt(
        {
            "ok": True,
            "terminal": {
                "merge_leftover_remaining": {
                    "ok": True,
                    "pass_dir": pass_dir,
                    "written": True,
                    "route": "merge",
                }
            },
        }
    )
    assert out["pass_dir"] == pass_dir


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


def test_seed_occupancy_ignores_prior_survey(monkeypatch):
    from lokay.proc.seed_factory_occupancy import run

    monkeypatch.setattr(
        "lokay.proc.seed_prior_catalog.live_issue_to_pr_receipts",
        lambda: [{"repo": "mikolaj92/Temida", "issue": 1}],
    )
    out = run({"working": {"ready_by_repo": {}, "occupied_repos": []}})
    assert out["working"]["ready_by_repo"] == {}
    assert "mikolaj92/Temida" in out["working"]["occupied_repos"]
    assert "mikolaj92/Temida" in out["working"]["live_issue_to_pr_repos"]


def test_attach_stuck_then_persist_writes_both_files(tmp_path):
    from lokay.proc.attach_factory_stuck import attach
    from lokay.proc.persist_factory_begin_state import persist as persist_begin
    from lokay.proc.persist_factory_tick import persist as persist_tick
    from lokay.proc.persist_factory_working_state import persist as persist_working
    from lokay.stuck import save_stuck

    stuck_path = tmp_path / "stuck.json"
    save_stuck(stuck_path, {"issues": {"a/b#1": {"blocked": True}}})
    pass_dir = tmp_path / "pass"
    pass_dir.mkdir()
    workspace = {"pass_dir": str(pass_dir)}
    attached = attach(
        {"begin": {"pass_dir": str(pass_dir), "stuck_path": str(stuck_path), "planned": []}},
        {"working": {"progress": 0}},
        {"stuck_path": str(stuck_path), "issue_count": 1},
    )
    persist_begin(workspace, attached)
    persist_working(workspace, attached)
    out = persist_tick(workspace, attached, {}, {"stuck_path": str(stuck_path), "issue_count": 1})
    assert out["ok"] is True
    assert out["pass_dir"] == str(pass_dir)
    assert out["idle"] is False
    begin = json.loads((pass_dir / "begin.json").read_text())
    working = json.loads((pass_dir / "working.json").read_text())
    tick = json.loads((pass_dir / "tick.json").read_text())
    assert "a/b#1" in begin["stuck"]["issues"]
    assert working["stuck"] == begin["stuck"]
    assert tick["idle"] is False
    assert tick["health"] != "idle"


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
