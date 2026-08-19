from __future__ import annotations

import json
from pathlib import Path

import pytest

from lokay.localize import Localization
from lokay.proc import relocalize_off_goal
from lokay.runner import Runner


class RecordingRunner(Runner):
    def __init__(self):
        super().__init__()
        self.specs = []

    def run_checked(self, spec, *, live):
        self.specs.append((spec, live))


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


def test_relocalize_restores_factory_begin_when_issue_does_not_name_it(
    monkeypatch, tmp_path: Path, capsys
):
    (tmp_path / ".lokay").mkdir()
    (tmp_path / ".lokay/localize.json").write_text(
        json.dumps({"paths": ["src/a.py"]}), encoding="utf-8"
    )
    issue = tmp_path / "issue.json"
    issue.write_text(json.dumps({"body": "## Files\n- `src/a.py`"}), encoding="utf-8")
    run = RecordingRunner()
    monkeypatch.setattr(relocalize_off_goal, "runner", lambda *a, **k: run)
    monkeypatch.setattr(
        relocalize_off_goal,
        "list_changed_paths",
        lambda *a, **k: ["src/a.py", "src/lokay/proc/factory_begin.py"],
    )
    monkeypatch.setattr(relocalize_off_goal, "load_cfg", lambda _a: object())
    monkeypatch.setattr(relocalize_off_goal, "mutations_allowed", lambda **k: True)

    assert relocalize_off_goal.main(
        ["--config", "x", "--live", "--worktree", str(tmp_path), "--issue-json", str(issue)]
    ) == 0

    out = json.loads(capsys.readouterr().out)
    assert out["reason"] == "factory_begin_restored"
    assert out["restored_paths"] == ["src/lokay/proc/factory_begin.py"]
    spec, live = run.specs[0]
    assert spec.argv == (
        "git", "restore", "--source", "origin/main", "--staged", "--worktree", "--",
        "src/lokay/proc/factory_begin.py",
    )
    assert live is True


def test_relocalize_restores_implement_when_issue_does_not_name_it(
    monkeypatch, tmp_path: Path, capsys
):
    (tmp_path / ".lokay").mkdir()
    (tmp_path / ".lokay/localize.json").write_text(
        json.dumps({"paths": ["src/a.py"]}), encoding="utf-8"
    )
    issue = tmp_path / "issue.json"
    issue.write_text(json.dumps({"body": "## Files\n- `src/a.py`"}), encoding="utf-8")
    path = "src/lokay/proc/implement.py"
    run = RecordingRunner()
    monkeypatch.setattr(relocalize_off_goal, "runner", lambda *a, **k: run)
    monkeypatch.setattr(relocalize_off_goal, "list_changed_paths", lambda *a, **k: [path])
    monkeypatch.setattr(relocalize_off_goal, "load_cfg", lambda _a: object())
    monkeypatch.setattr(relocalize_off_goal, "mutations_allowed", lambda **k: True)

    assert relocalize_off_goal.main(
        ["--config", "x", "--live", "--worktree", str(tmp_path), "--issue-json", str(issue)]
    ) == 0

    out = json.loads(capsys.readouterr().out)
    assert out["reason"] == "implement_restored"
    assert out["restored_paths"] == [path]
    spec, live = run.specs[0]
    assert spec.argv == (
        "git", "restore", "--source", "origin/main", "--staged", "--worktree", "--", path,
    )
    assert live is True


def test_relocalize_restores_agent_when_issue_does_not_name_it(
    monkeypatch, tmp_path: Path, capsys
):
    (tmp_path / ".lokay").mkdir()
    (tmp_path / ".lokay/localize.json").write_text(
        json.dumps({"paths": ["src/a.py"]}), encoding="utf-8"
    )
    issue = tmp_path / "issue.json"
    issue.write_text(json.dumps({"body": "## Files\n- `src/a.py`"}), encoding="utf-8")
    path = "src/lokay/organ/agent.py"
    run = RecordingRunner()
    monkeypatch.setattr(relocalize_off_goal, "runner", lambda *a, **k: run)
    monkeypatch.setattr(relocalize_off_goal, "list_changed_paths", lambda *a, **k: [path])
    monkeypatch.setattr(relocalize_off_goal, "load_cfg", lambda _a: object())
    monkeypatch.setattr(relocalize_off_goal, "mutations_allowed", lambda **k: True)

    assert relocalize_off_goal.main(
        ["--config", "x", "--live", "--worktree", str(tmp_path), "--issue-json", str(issue)]
    ) == 0

    out = json.loads(capsys.readouterr().out)
    assert out["reason"] == "agent_restored"
    assert out["restored_paths"] == [path]
    spec, live = run.specs[0]
    assert spec.argv == (
        "git", "restore", "--source", "origin/main", "--staged", "--worktree", "--", path,
    )
    assert live is True


@pytest.mark.parametrize(
    "path",
    [
        "fala/lokay.fala-package.toml",
        "src/lokay/data/lokay.fala-package.toml",
    ],
)
def test_relocalize_restores_fala_package_when_issue_does_not_name_it(
    path: str, monkeypatch, tmp_path: Path, capsys
):
    (tmp_path / ".lokay").mkdir()
    (tmp_path / ".lokay/localize.json").write_text(
        json.dumps({"paths": ["src/a.py"]}), encoding="utf-8"
    )
    issue = tmp_path / "issue.json"
    issue.write_text(json.dumps({"body": "## Files\n- `src/a.py`"}), encoding="utf-8")
    run = RecordingRunner()
    monkeypatch.setattr(relocalize_off_goal, "runner", lambda *a, **k: run)
    monkeypatch.setattr(relocalize_off_goal, "list_changed_paths", lambda *a, **k: [path])
    monkeypatch.setattr(relocalize_off_goal, "load_cfg", lambda _a: object())
    monkeypatch.setattr(relocalize_off_goal, "mutations_allowed", lambda **k: True)

    assert relocalize_off_goal.main(
        ["--config", "x", "--live", "--worktree", str(tmp_path), "--issue-json", str(issue)]
    ) == 0

    out = json.loads(capsys.readouterr().out)
    assert out["reason"] == "off_goal_paths_restored"
    assert out["restored_paths"] == [path]
    spec, live = run.specs[0]
    assert spec.argv == (
        "git", "restore", "--source", "origin/main", "--staged", "--worktree", "--", path,
    )
    assert live is True


@pytest.mark.parametrize(
    "path",
    [
        "fala/lokay.fala-package.toml",
        "src/lokay/data/lokay.fala-package.toml",
    ],
)
def test_relocalize_keeps_fala_package_when_issue_names_it(
    path: str, monkeypatch, tmp_path: Path, capsys
):
    (tmp_path / ".lokay").mkdir()
    (tmp_path / ".lokay/localize.json").write_text(
        json.dumps({"paths": [path]}), encoding="utf-8"
    )
    issue = tmp_path / "issue.json"
    issue.write_text(json.dumps({"body": f"## Zmiana\n- `{path}`"}), encoding="utf-8")
    run = RecordingRunner()
    monkeypatch.setattr(relocalize_off_goal, "runner", lambda *a, **k: run)
    monkeypatch.setattr(relocalize_off_goal, "list_changed_paths", lambda *a, **k: [path])
    monkeypatch.setattr(relocalize_off_goal, "load_cfg", lambda _a: object())

    assert relocalize_off_goal.main(
        ["--config", "x", "--live", "--worktree", str(tmp_path), "--issue-json", str(issue)]
    ) == 0

    out = json.loads(capsys.readouterr().out)
    assert out["reason"] == "on_goal"
    assert out["restored_paths"] == []
    assert run.specs == []


def test_relocalize_keeps_agent_when_issue_names_it(
    monkeypatch, tmp_path: Path, capsys
):
    (tmp_path / ".lokay").mkdir()
    path = "src/lokay/organ/agent.py"
    (tmp_path / ".lokay/localize.json").write_text(
        json.dumps({"paths": [path]}), encoding="utf-8"
    )
    issue = tmp_path / "issue.json"
    issue.write_text(json.dumps({"body": f"## Zmiana\n- `{path}`"}), encoding="utf-8")
    run = RecordingRunner()
    monkeypatch.setattr(relocalize_off_goal, "runner", lambda *a, **k: run)
    monkeypatch.setattr(relocalize_off_goal, "list_changed_paths", lambda *a, **k: [path])
    monkeypatch.setattr(relocalize_off_goal, "load_cfg", lambda _a: object())

    assert relocalize_off_goal.main(
        ["--config", "x", "--live", "--worktree", str(tmp_path), "--issue-json", str(issue)]
    ) == 0

    out = json.loads(capsys.readouterr().out)
    assert out["reason"] == "on_goal"
    assert out["restored_paths"] == []
    assert run.specs == []


def test_relocalize_keeps_implement_when_issue_names_it(
    monkeypatch, tmp_path: Path, capsys
):
    (tmp_path / ".lokay").mkdir()
    path = "src/lokay/proc/implement.py"
    (tmp_path / ".lokay/localize.json").write_text(
        json.dumps({"paths": [path]}), encoding="utf-8"
    )
    issue = tmp_path / "issue.json"
    issue.write_text(json.dumps({"body": f"## Files\n- `{path}`"}), encoding="utf-8")
    run = RecordingRunner()
    monkeypatch.setattr(relocalize_off_goal, "runner", lambda *a, **k: run)
    monkeypatch.setattr(relocalize_off_goal, "list_changed_paths", lambda *a, **k: [path])
    monkeypatch.setattr(relocalize_off_goal, "load_cfg", lambda _a: object())

    assert relocalize_off_goal.main(
        ["--config", "x", "--live", "--worktree", str(tmp_path), "--issue-json", str(issue)]
    ) == 0

    out = json.loads(capsys.readouterr().out)
    assert out["reason"] == "on_goal"
    assert out["restored_paths"] == []
    assert run.specs == []


def test_relocalize_keeps_factory_begin_when_issue_names_it(
    monkeypatch, tmp_path: Path, capsys
):
    (tmp_path / ".lokay").mkdir()
    path = "src/lokay/proc/factory_begin.py"
    (tmp_path / ".lokay/localize.json").write_text(
        json.dumps({"paths": [path]}), encoding="utf-8"
    )
    issue = tmp_path / "issue.json"
    issue.write_text(json.dumps({"body": f"## Zmiana\n- `{path}`"}), encoding="utf-8")
    run = RecordingRunner()
    monkeypatch.setattr(relocalize_off_goal, "runner", lambda *a, **k: run)
    monkeypatch.setattr(relocalize_off_goal, "list_changed_paths", lambda *a, **k: [path])
    monkeypatch.setattr(relocalize_off_goal, "load_cfg", lambda _a: object())

    assert relocalize_off_goal.main(
        ["--config", "x", "--live", "--worktree", str(tmp_path), "--issue-json", str(issue)]
    ) == 0

    out = json.loads(capsys.readouterr().out)
    assert out["reason"] == "on_goal"
    assert out["restored_paths"] == []
    assert run.specs == []
