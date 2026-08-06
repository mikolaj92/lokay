"""DoD status: mill_ready and blockers."""

from pathlib import Path

from lokay.compose.status import compose_status


def test_status_reports_blockers_when_dry(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LOKAY_OFFLINE", "1")
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        f"""
mode: dry-run
repos:
  - name: a/b
    clone_path: {tmp_path}
executor:
  enabled: false
  agent: grok
merge:
  enabled: false
  require_checks: true
worktrees:
  root: {tmp_path / "wt"}
state:
  path: {tmp_path / "state.jsonl"}
""",
        encoding="utf-8",
    )
    result = compose_status(config_path=str(cfg_path))
    assert result["mill_ready"] is False
    assert any("mode is not live" in b for b in result["blockers"])
    assert any("executor.enabled" in b for b in result["blockers"])
    assert any("merge.enabled" in b for b in result["blockers"])


def test_require_checks_is_policy_not_hard_blocker(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LOKAY_OFFLINE", "1")
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
  require_checks: true
worktrees:
  root: {tmp_path / "wt"}
state:
  path: {tmp_path / "state.jsonl"}
""",
        encoding="utf-8",
    )
    result = compose_status(config_path=str(cfg_path))
    assert result["mill_ready"] is True
    assert result["blockers"] == []
    assert any("require_checks" in n for n in result.get("policy_notes") or [])
