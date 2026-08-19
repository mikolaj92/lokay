from __future__ import annotations

import json
from pathlib import Path

from lokay.localize import Localization
from lokay.proc import relocalize_off_goal


def test_relocalize_skips_when_agent_does_not_approve(monkeypatch, tmp_path: Path, capsys):
    (tmp_path / ".lokay").mkdir()
    (tmp_path / ".lokay/localize.json").write_text(
        json.dumps({"paths": ["src/a.py"]}), encoding="utf-8"
    )
    monkeypatch.setattr(relocalize_off_goal, "list_changed_paths", lambda *a, **k: ["src/a.py", "src/b.py"])
    monkeypatch.setattr(relocalize_off_goal, "load_cfg", lambda _a: object())
    monkeypatch.setattr(relocalize_off_goal, "semantic_agent_allowed", lambda *a, **k: True)
    monkeypatch.setattr(
        relocalize_off_goal,
        "build_localization_with_agent",
        lambda **k: Localization(
            paths=("src/a.py",),
            source="agent",
            semantic={"kind": "localize", "source": "agent", "status": "completed"},
        ),
    )
    assert relocalize_off_goal.main(["--config", "x", "--live", "--worktree", str(tmp_path)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["skipped"] is True
    assert out["reason"] == "off_goal_not_approved"


def test_relocalize_writes_one_approved_path(monkeypatch, tmp_path: Path, capsys):
    (tmp_path / ".lokay").mkdir()
    (tmp_path / ".lokay/localize.json").write_text(
        json.dumps({"paths": ["src/a.py"]}), encoding="utf-8"
    )
    monkeypatch.setattr(relocalize_off_goal, "list_changed_paths", lambda *a, **k: ["src/a.py", "src/b.py"])
    monkeypatch.setattr(relocalize_off_goal, "load_cfg", lambda _a: object())
    monkeypatch.setattr(relocalize_off_goal, "semantic_agent_allowed", lambda *a, **k: True)
    monkeypatch.setattr(relocalize_off_goal, "mutations_allowed", lambda **k: True)
    monkeypatch.setattr(
        relocalize_off_goal,
        "build_localization_with_agent",
        lambda **k: Localization(
            paths=("src/a.py", "src/b.py"),
            source="agent",
            semantic={"kind": "localize", "source": "agent", "status": "completed"},
        ),
    )
    assert relocalize_off_goal.main(["--config", "x", "--live", "--worktree", str(tmp_path)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["approved_paths"] == ["src/b.py"]
    saved = json.loads((tmp_path / ".lokay/localize.json").read_text(encoding="utf-8"))
    assert saved["paths"] == ["src/a.py", "src/b.py"]
