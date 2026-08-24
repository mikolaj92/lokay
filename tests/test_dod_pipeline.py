"""Drive shipped assign / pr_create / pr_merge mains — issue→PR→merge envelopes."""

from __future__ import annotations

import json
from pathlib import Path

from lokay.proc import assign_issue, pr_merge
from lokay.runner import CommandResult, CommandSpec


def _cfg(tmp_path: Path, *, mode: str = "dry-run", merge_enabled: bool = True) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(
        f"""
mode: {mode}
github:
  assignee: mill-bot
merge:
  enabled: {str(merge_enabled).lower()}
repos: []
""",
        encoding="utf-8",
    )
    return path


class _GhRunner:
    def __init__(self, *, stdout: str = "", returncode: int = 0) -> None:
        self.stdout = stdout
        self.returncode = returncode
        self.calls: list[tuple[str, ...]] = []

    def run(self, spec: CommandSpec, *, live: bool) -> CommandResult:
        self.calls.append(tuple(spec.argv))
        return CommandResult(
            spec=spec, executed=live, returncode=self.returncode, stdout=self.stdout
        )

    def run_checked(self, spec: CommandSpec, *, live: bool) -> CommandResult:
        return self.run(spec, live=live)


def _envelope(capsys) -> dict:
    return json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def test_assign_dry_run_reports_self_assignee(tmp_path, capsys):
    cfg = _cfg(tmp_path)
    code = assign_issue.main(
        ["--config", str(cfg), "--repo", "mikolaj92/lokay", "--issue", "164"]
    )
    assert code == 0
    env = _envelope(capsys)
    assert env["ok"] is True
    assert env["planned"] is True
    assert env["applied"] is False
    assert env["assignee"] == "mill-bot"
    assert env["repo"] == "mikolaj92/lokay"
    assert env["issue"] == 164


def test_assign_live_fixture_applies_configured_self(tmp_path, monkeypatch, capsys):
    cfg = _cfg(tmp_path, mode="live")
    runner = _GhRunner()
    monkeypatch.setattr(assign_issue, "runner", lambda: runner)
    monkeypatch.setattr(assign_issue, "mutations_allowed", lambda **k: True)
    code = assign_issue.main(
        ["--config", str(cfg), "--live", "--repo", "mikolaj92/lokay", "--issue", "164"]
    )
    assert code == 0
    env = _envelope(capsys)
    assert env["ok"] is True
    assert env["applied"] is True
    assert env["assignee"] == "mill-bot"
    joined = " ".join(" ".join(c) for c in runner.calls)
    assert "--add-assignee mill-bot" in joined
    assert "164" in joined


def test_pr_create_after_push_shaped_success_has_number():
    from lokay.proc.pr_create_terminal import terminal

    out = terminal(
        {"repo": "a/b", "head": "ai/fix/1", "issue": 1},
        {"route": "none"},
        {"issue_state": "OPEN"},
        {"route": "create"},
        {"route": "created", "pull": {"number": 239}, "planned": False},
    )["result"]
    assert out["ok"] is True and out["pr"] == 239 and out["planned"] is False


def test_pr_create_dry_run_has_planned_pr_fields():
    from lokay.proc.pr_create_terminal import terminal

    out = terminal(
        {"repo": "a/b", "head": "ai/fix/1", "issue": 1},
        {"route": "none"},
        {"issue_state": "OPEN"},
        {"route": "create"},
        {"route": "created", "pull": {"number": None}, "planned": True},
    )["result"]
    assert out["ok"] is True and out["planned"] is True and out["existing"] is False


def test_pr_merge_mergeable_reports_merged(tmp_path, monkeypatch, capsys):
    cfg = _cfg(tmp_path, mode="live")
    runner = _GhRunner()
    monkeypatch.setattr(pr_merge, "runner", lambda: runner)
    monkeypatch.setattr(pr_merge, "mutations_allowed", lambda **k: True)
    monkeypatch.setattr(
        pr_merge,
        "run_proc",
        lambda *_args: (_ for _ in ()).throw(
            AssertionError("merge without issue must not park")
        ),
    )
    code = pr_merge.main(
        ["--config", str(cfg), "--live", "--repo", "mikolaj92/lokay", "--pr", "88"]
    )
    assert code == 0
    env = _envelope(capsys)
    assert env["ok"] is True
    assert env["merged"] is True
    assert env["repo"] == "mikolaj92/lokay"
    assert env["pr"] == 88
    joined = " ".join(runner.calls[0])
    assert "pr merge" in joined and "88" in joined


def test_pr_merge_with_issue_parks_ready_labels(tmp_path, monkeypatch, capsys):
    cfg = _cfg(tmp_path, mode="live")
    runner = _GhRunner()
    parked: list[list[str]] = []
    monkeypatch.setattr(pr_merge, "runner", lambda: runner)
    monkeypatch.setattr(pr_merge, "mutations_allowed", lambda **k: True)
    monkeypatch.setattr(
        pr_merge,
        "run_proc",
        lambda _main, argv: parked.append(argv) or {"ok": True, "removed": True},
    )

    code = pr_merge.main(
        [
            "--config",
            str(cfg),
            "--live",
            "--repo",
            "mikolaj92/lokay",
            "--pr",
            "88",
            "--issue",
            "164",
        ]
    )

    assert code == 0
    env = _envelope(capsys)
    assert env["ok"] is True
    assert env["merged"] is True
    assert env["issue"] == 164
    assert env["parked"]["removed"] is True
    assert parked == [
        [
            "--config",
            str(cfg),
            "--live",
            "--repo",
            "mikolaj92/lokay",
            "--issue",
            "164",
        ]
    ]


def test_pr_merge_dry_run_does_not_park_issue(tmp_path, monkeypatch, capsys):
    cfg = _cfg(tmp_path)
    monkeypatch.setattr(
        pr_merge,
        "run_proc",
        lambda *_args: (_ for _ in ()).throw(AssertionError("dry-run must not park")),
    )
    code = pr_merge.main(
        [
            "--config",
            str(cfg),
            "--repo",
            "mikolaj92/lokay",
            "--pr",
            "88",
            "--issue",
            "164",
        ]
    )
    assert code == 0
    env = _envelope(capsys)
    assert env["ok"] is True
    assert env["planned"] is True
    assert env["merged"] is False
    assert env["pr"] == 88
    assert env["issue"] == 164
    assert env["parked"] is None
