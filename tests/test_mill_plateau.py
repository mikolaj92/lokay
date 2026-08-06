"""Mill must not burn pass budget on green-noop progress."""

from __future__ import annotations

from lokay.compose import mill as mill_mod


def test_mill_plateau_stops_when_remaining_unchanged(monkeypatch, tmp_path):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        f"""
mode: live
repos:
  - name: a/b
    clone_path: {tmp_path}
executor:
  enabled: true
  agent: grok
merge:
  enabled: true
  require_checks: false
worktrees:
  root: {tmp_path / "wt"}
state:
  path: {tmp_path / "state.jsonl"}
""",
        encoding="utf-8",
    )
    remaining = {
        "inbox": 2,
        "ready": 0,
        "open_ai_prs": 1,
        "mergeable_green": 0,
        "needs_repair": 0,
        "no_checks_blocked": 1,
        "merge_conflicts": 0,
        "survey_errors": 0,
    }
    calls = {"n": 0}

    def fake_tick(*, config_path=None, live=False):
        calls["n"] += 1
        return {
            "ok": True,
            "idle": False,
            "health": "progress",
            "progress": 2,
            "remaining": dict(remaining),
        }

    monkeypatch.setattr(mill_mod, "compose_tick", fake_tick)
    out = mill_mod.compose_mill(config_path=str(cfg_path), live=True, max_passes=8)
    assert out["ok"] is False
    assert out["health"] == "plateau"
    # first pass records baseline, second pass detects plateau
    assert calls["n"] == 2
    assert out["passes"] == 2
