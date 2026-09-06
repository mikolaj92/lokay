"""Contracts for in-process self-repair untracked catalog."""


def test_catalog_empty_paths_reduces_tracked():
    from lokay.proc.self_repair_untracked_catalog import run

    out = run({"ok": True, "route": "paths", "paths": [], "worktree": "/tmp/w"})
    assert out["ok"] is True and out["route"] == "tracked"


def test_catalog_stops_on_invalid(monkeypatch):
    from lokay.proc import self_repair_untracked_catalog as cat

    calls = {"n": 0}

    def fake_check(selected):
        calls["n"] += 1
        return {**selected, "ok": False, "route": "invalid", "error": "bad"}

    monkeypatch.setattr(
        "lokay.proc.check_self_repair_untracked_path.check", fake_check
    )
    out = cat.run(
        {
            "ok": True,
            "route": "paths",
            "paths": ["a.py", "b.py"],
            "worktree": "/tmp/w",
        }
    )
    assert out["ok"] is False and out["route"] == "invalid"
    assert calls["n"] == 1


def test_listed_not_ok_passthrough():
    from lokay.proc.self_repair_untracked_catalog import run

    listed = {"ok": False, "error": "overflow"}
    assert run(listed) == listed
