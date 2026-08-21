"""Factory pass workspace scope."""

from __future__ import annotations

import json
from pathlib import Path

from lokay.proc.factory_begin import run_factory_begin


def test_mini_begin_repos_contains_only_lokay(tmp_path: Path, monkeypatch) -> None:
    config = tmp_path / "config.yaml"
    config.write_text(
        f"""
mode: dry-run
repos:
  - name: mikolaj92/Temida
    clone_path: {tmp_path / "Temida"}
  - name: mikolaj92/lokay
    clone_path: {tmp_path / "lokay"}
state:
  path: {tmp_path / "state.jsonl"}
executor:
  enabled: false
""",
        encoding="utf-8",
    )
    monkeypatch.delenv("LOKAY_OFFLINE", raising=False)
    monkeypatch.setattr(
        "lokay.proc.factory_begin.harvest_fail_closed_children",
        lambda *_args, **_kwargs: None,
    )

    result = run_factory_begin(config_path=str(config), live=False)

    assert result["ok"] is True
    begin = json.loads(
        (Path(result["pass_dir"]) / "begin.json").read_text(encoding="utf-8")
    )
    assert begin["repos"] == ["mikolaj92/lokay"]
    assert begin["survey_repos"] == ["mikolaj92/lokay"]
    assert begin["planned"][0]["repos"] == ["mikolaj92/lokay"]


def test_mini_begin_harvests_only_lokay_stuck_rows(tmp_path: Path, monkeypatch) -> None:
    seen: dict[str, object] = {}

    def fake_harvest(stuck, *, state_path, repos=None, **_kwargs):
        seen["repos"] = repos
        return stuck

    config = tmp_path / "config.yaml"
    config.write_text(
        f"""
mode: dry-run
repos:
  - name: mikolaj92/Temida
    clone_path: {tmp_path / "Temida"}
  - name: mikolaj92/lokay
    clone_path: {tmp_path / "lokay"}
state:
  path: {tmp_path / "state.jsonl"}
executor:
  enabled: false
""",
        encoding="utf-8",
    )
    monkeypatch.delenv("LOKAY_OFFLINE", raising=False)
    monkeypatch.setattr(
        "lokay.proc.factory_begin.harvest_fail_closed_children",
        fake_harvest,
    )

    result = run_factory_begin(config_path=str(config), live=False)

    assert result["ok"] is True
    assert seen["repos"] == ["mikolaj92/lokay"]
