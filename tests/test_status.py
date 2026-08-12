"""DoD status: mill_ready and blockers."""

from pathlib import Path

from lokay.cli import build_parser
from lokay.compose.status import compose_status


def _write_cfg(tmp_path: Path, *, mode: str, executor: bool, merge: bool) -> Path:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        f"""
mode: {mode}
repos:
  - name: a/b
    clone_path: {tmp_path}
executor:
  enabled: {str(executor).lower()}
  agent: grok
merge:
  enabled: {str(merge).lower()}
  require_checks: true
worktrees:
  root: {tmp_path / "wt"}
state:
  path: {tmp_path / "state.jsonl"}
""",
        encoding="utf-8",
    )
    return cfg_path


def test_status_reports_blockers_when_dry(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LOKAY_OFFLINE", "1")
    cfg_path = _write_cfg(tmp_path, mode="dry-run", executor=False, merge=False)
    result = compose_status(config_path=str(cfg_path))
    assert result["mill_ready"] is False
    assert any("mode is not live" in b for b in result["blockers"])
    assert any("executor.enabled" in b for b in result["blockers"])
    assert any("merge.enabled" in b for b in result["blockers"])
    assert "LOKAY_AGENT" not in result["live_env_hint"]


def test_require_checks_is_policy_not_hard_blocker(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LOKAY_OFFLINE", "1")
    cfg_path = _write_cfg(tmp_path, mode="live", executor=True, merge=True)
    result = compose_status(config_path=str(cfg_path))
    assert result["mill_ready"] is True
    assert result["blockers"] == []
    assert any("require_checks" in n for n in result.get("policy_notes") or [])


def test_local_status_skips_survey(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("LOKAY_OFFLINE", raising=False)
    cfg_path = _write_cfg(tmp_path, mode="live", executor=True, merge=True)

    def boom(*_a, **_k):
        raise AssertionError("full survey must not run on --local")

    monkeypatch.setattr("lokay.compose.status.compose_tick", boom)
    result = compose_status(config_path=str(cfg_path), survey=False)
    assert result["ok"] is True
    assert result["survey"] is False
    assert result["mill_ready"] is True
    assert result["health"] == "local"
    assert result["remaining"] == {"note": "survey_skipped"}
    assert result["idle"] is None
    assert "lease_ok" in result
    assert "lease_reason" in result


def test_local_status_still_fails_when_not_mill_ready(tmp_path: Path, monkeypatch):
    cfg_path = _write_cfg(tmp_path, mode="dry-run", executor=False, merge=False)
    monkeypatch.setattr(
        "lokay.compose.status.compose_tick",
        lambda **k: (_ for _ in ()).throw(AssertionError("survey")),
    )
    result = compose_status(config_path=str(cfg_path), survey=False)
    assert result["ok"] is False
    assert result["survey"] is False
    assert result["mill_ready"] is False


def test_cli_status_local_flag_wiring():
    parser = build_parser()
    args = parser.parse_args(["status", "--local", "--config", "c.yaml"])
    assert args.local is True
    args_skip = parser.parse_args(["status", "--skip-survey"])
    assert args_skip.local is True


def test_mill_daemon_does_not_override_configured_executor_metadata():
    root = Path(__file__).resolve().parents[1]
    script = (root / "scripts" / "lokay-mill-daemon.sh").read_text(encoding="utf-8")
    assert 'export LOKAY_AGENT=' not in script
    assert 'LOKAY_AGENT:-grok' not in script
