"""Live mill atoms write activity.json beside state.jsonl."""

from __future__ import annotations

import json
from pathlib import Path

from lokay import fala_organ
from lokay.proc.classify_pass_ceiling import classify


def _cfg(tmp_path: Path) -> str:
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        f"""
mode: dry-run
repos:
  - name: a/b
    clone_path: {tmp_path}
executor:
  enabled: false
  command: true
  args: ["{{prompt}}"]
state:
  path: {tmp_path / "state.jsonl"}
""",
        encoding="utf-8",
    )
    return str(cfg)


def test_organ_writes_activity_before_atom(tmp_path: Path):
    cfg = _cfg(tmp_path)
    fala_organ._handle(
        "classify_daemon_preflight",
        {"config_path": cfg, "preflight": {"ok": True}, "repo": "mikolaj92/reviewkit", "issue": 308},
        {},
    )
    payload = json.loads((tmp_path / "activity.json").read_text(encoding="utf-8"))
    assert payload["atom"] == "classify_daemon_preflight"
    assert payload["transitions"] == 1
    assert payload["repo"] == "mikolaj92/reviewkit"
    assert payload["work_id"] == "mikolaj92/reviewkit#308"
    assert payload["last_progress_at"]


def test_organ_increments_transitions(tmp_path: Path):
    cfg = _cfg(tmp_path)
    fala_organ._handle(
        "classify_daemon_preflight",
        {"config_path": cfg, "preflight": {"ok": True}},
        {},
    )
    fala_organ._handle(
        "classify_daemon_preflight",
        {"config_path": cfg, "preflight": {"ok": False, "operational_overlap": True}},
        {},
    )
    payload = json.loads((tmp_path / "activity.json").read_text(encoding="utf-8"))
    assert payload["transitions"] == 2
    assert payload["atom"] == "classify_daemon_preflight"


def test_process_id_fills_path(tmp_path: Path):
    from lokay.activity import record_atom_start

    cfg = _cfg(tmp_path)
    record_atom_start(
        atom="host_ff",
        inputs={"config_path": cfg, "repo": "mikolaj92/lokay"},
        process_id="factory_pass:host_ff",
    )
    payload = json.loads((tmp_path / "activity.json").read_text(encoding="utf-8"))
    assert payload["path"] == "factory_pass"
    assert payload["atom"] == "host_ff"
    ceiling = classify(state_dir=tmp_path, elapsed_seconds=180)
    assert ceiling["reason"] == "ceiling_with_progress"
    assert ceiling["resume_from"] == "factory_pass"
    assert ceiling["last_atom"] == "host_ff"


def test_missing_activity_still_classifies_without_crash(tmp_path: Path):
    out = classify(state_dir=tmp_path, elapsed_seconds=180)
    assert out["reason"] == "ceiling_stalled"
    assert out["transitions"] == 0
    assert "resume_from" not in out


def test_write_failure_does_not_raise(tmp_path: Path, monkeypatch):
    from lokay import activity

    cfg = _cfg(tmp_path)

    def boom(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(activity.Path, "write_text", boom)
    assert (
        activity.record_atom_start(
            atom="host_ff",
            inputs={"config_path": cfg},
        )
        is None
    )
