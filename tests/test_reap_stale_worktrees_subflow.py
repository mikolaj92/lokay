"""Leftover work-copy cleanup: classified failed route, never process.failed."""

from lokay.organ.factory import handle_factory
from lokay.proc.classify_stale_worktree_reap import classify, failed
from lokay.proc.reap_stale_worktrees_subflow import run


FIRE_STEP = "sqlite.fire: failed to step query"


def test_failed_helper_is_succeeded_classified_route():
    out = failed(FIRE_STEP)
    assert out["ok"] is True
    assert out["route"] == "failed"
    assert out["result"]["route"] == "failed"
    assert FIRE_STEP in str(out["error"])


def test_cleanup_systemexit_yields_route(monkeypatch):
    def boom(**_kwargs):
        raise SystemExit("cleanup process.failed")

    monkeypatch.setattr("lokay.proc.reap_stale_worktrees_subflow.run_path", boom)
    out = run(pass_dir="/pass", config_path=None, live=False)
    assert out["ok"] is True
    assert out["route"] == "failed"


def test_cleanup_throw_yields_route(monkeypatch):
    def boom(**_kwargs):
        raise RuntimeError(FIRE_STEP)

    monkeypatch.setattr("lokay.proc.reap_stale_worktrees_subflow.run_path", boom)
    out = run(pass_dir="/pass", config_path=None, live=False)
    assert out["ok"] is True
    assert out["route"] == "failed"
    assert FIRE_STEP in str(out["error"])


def test_cleanup_not_ok_yields_route(monkeypatch):
    monkeypatch.setattr(
        "lokay.proc.reap_stale_worktrees_subflow.run_path",
        lambda **_k: {"ok": False, "error": FIRE_STEP},
    )
    out = run(pass_dir="/pass", config_path=None, live=False)
    assert out["ok"] is True
    assert out["route"] == "failed"


def test_empty_cleanup_yields_classified_route(monkeypatch):
    monkeypatch.setattr(
        "lokay.proc.reap_stale_worktrees_subflow.run_path",
        lambda **_k: {"ok": True, "route": "", "result": {}},
    )
    out = run(pass_dir="/pass", config_path=None, live=False)
    assert out["ok"] is True
    assert out["route"] == "failed"


def test_empty_dict_cleanup_yields_classified_route():
    out = classify({})
    assert out["ok"] is True
    assert out["route"] == "failed"


def test_successful_cleanup_is_cleaned():
    out = classify({"ok": True, "result": {"reaped_count": 0, "kept_count": 2}})
    assert out["ok"] is True
    assert out["route"] == "cleaned"


def test_overflow_skip_is_skip():
    out = classify(
        {"ok": True, "result": {"skipped": True, "reason": "stale_worktree_overflow"}}
    )
    assert out["ok"] is True
    assert out["route"] == "skip"


def test_cleanup_failure_does_not_mark_factory_adapter_failed(monkeypatch):
    monkeypatch.setattr(
        "lokay.proc.reap_stale_worktrees_subflow.run_path",
        lambda **_k: {"ok": False, "error": FIRE_STEP},
    )
    out = handle_factory(
        "reap_stale_worktrees",
        {"live": False},
        {"factory_begin": {"pass_dir": "/pass"}},
        {
            "cfg": [],
            "live": [],
            "repo": "local/worktrees",
            "issue_number": None,
            "pr_number": None,
            "repair_mode": False,
            "branch": "",
        },
    )
    assert out is not None
    assert out["ok"] is True
    assert out["route"] == "failed"
    assert out.get("status") != "failed"
    assert out.get("_exit", 0) == 0
    assert FIRE_STEP in str(out.get("error") or "")


def test_empty_pass_dir_is_classified_without_cwd_begin(monkeypatch, tmp_path):
    """Empty pass_dir is route=failed; never open CWD begin.json."""
    called = {"run_path": False, "load": False}

    def boom(**_kwargs):
        called["run_path"] = True
        raise AssertionError("run_path must not run with empty pass_dir")

    def load_boom(pass_dir):
        called["load"] = True
        raise AssertionError(f"load_begin_working must not open {pass_dir!r}")

    monkeypatch.setattr("lokay.proc.reap_stale_worktrees_subflow.run_path", boom)
    monkeypatch.setattr(
        "lokay.passkit.working.load_begin_working",
        load_boom,
    )
    monkeypatch.chdir(tmp_path)
    (tmp_path / "begin.json").write_text("{}", encoding="utf-8")
    out = run(pass_dir="", config_path=None, live=False)
    assert out["ok"] is True
    assert out["route"] == "failed"
    assert "empty pass_dir" in str(out["error"])
    assert called["run_path"] is False
    assert called["load"] is False


def test_whitespace_pass_dir_is_classified_without_cwd_begin(monkeypatch, tmp_path):
    called = {"run_path": False}

    def boom(**_kwargs):
        called["run_path"] = True
        raise AssertionError("run_path must not run")

    monkeypatch.setattr("lokay.proc.reap_stale_worktrees_subflow.run_path", boom)
    monkeypatch.chdir(tmp_path)
    out = run(pass_dir="   ", config_path=None, live=False)
    assert out["ok"] is True
    assert out["route"] == "failed"
    assert called["run_path"] is False

