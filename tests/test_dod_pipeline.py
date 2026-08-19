"""Drive shipped assign / pr_create / pr_merge mains — issue→PR→merge envelopes."""

from __future__ import annotations

import json
from pathlib import Path

from lokay.proc import assign_issue, pr_create, pr_merge
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
        ["--config", str(cfg), "--repo", "mikolaj92/Fala", "--issue", "164"]
    )
    assert code == 0
    env = _envelope(capsys)
    assert env["ok"] is True
    assert env["planned"] is True
    assert env["applied"] is False
    assert env["assignee"] == "mill-bot"
    assert env["repo"] == "mikolaj92/Fala"
    assert env["issue"] == 164


def test_assign_live_fixture_applies_configured_self(tmp_path, monkeypatch, capsys):
    cfg = _cfg(tmp_path, mode="live")
    runner = _GhRunner()
    monkeypatch.setattr(assign_issue, "runner", lambda: runner)
    monkeypatch.setattr(assign_issue, "mutations_allowed", lambda **k: True)
    code = assign_issue.main(
        ["--config", str(cfg), "--live", "--repo", "mikolaj92/Fala", "--issue", "164"]
    )
    assert code == 0
    env = _envelope(capsys)
    assert env["ok"] is True
    assert env["applied"] is True
    assert env["assignee"] == "mill-bot"
    joined = " ".join(" ".join(c) for c in runner.calls)
    assert "--add-assignee mill-bot" in joined
    assert "164" in joined


def test_pr_create_after_push_shaped_success_has_number(tmp_path, monkeypatch, capsys):
    cfg = _cfg(tmp_path, mode="live")
    runner = _GhRunner(stdout="https://github.com/mikolaj92/Fala/pull/88\n")
    monkeypatch.setattr(pr_create, "runner", lambda: runner)
    monkeypatch.setattr(pr_create, "mutations_allowed", lambda **k: True)
    code = pr_create.main(
        [
            "--config",
            str(cfg),
            "--live",
            "--repo",
            "mikolaj92/Fala",
            "--title",
            "fix: Fala#164 readme",
            "--body",
            "Closes #164",
            "--head",
            "ai/fix/164-x",
        ]
    )
    assert code == 0
    env = _envelope(capsys)
    assert env["ok"] is True
    assert env["pr"] == 88
    assert env["pull"]["number"] == 88
    assert "pr create" in " ".join(runner.calls[0])
    assert "--head" in runner.calls[0]


def test_pr_create_dry_run_has_planned_pr_fields(tmp_path, capsys):
    cfg = _cfg(tmp_path)
    code = pr_create.main(
        [
            "--config",
            str(cfg),
            "--repo",
            "mikolaj92/Fala",
            "--title",
            "fix: planned",
            "--body",
            "body",
            "--head",
            "ai/fix/1-x",
        ]
    )
    assert code == 0
    env = _envelope(capsys)
    assert env["ok"] is True
    assert env["planned"] is True
    assert env["pull"]["planned"] is True
    assert env["pull"]["head"] == "ai/fix/1-x"
    assert env["pr"] is None


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
    assert parked == [["--repo", "mikolaj92/lokay", "--issue", "164"]]


def test_pr_merge_refuses_product_repo_without_calling_gh(
    tmp_path, monkeypatch, capsys
):
    cfg = _cfg(tmp_path, mode="live")
    monkeypatch.setattr(pr_merge, "mutations_allowed", lambda **k: True)
    monkeypatch.setattr(
        pr_merge,
        "runner",
        lambda: (_ for _ in ()).throw(
            AssertionError("gh must not run for a product repo")
        ),
    )

    code = pr_merge.main(
        ["--config", str(cfg), "--live", "--repo", "mikolaj92/temida", "--pr", "88"]
    )

    assert code == 1
    env = _envelope(capsys)
    assert env["ok"] is False
    assert "refusing" in env["error"]
    assert env["repo"] == "mikolaj92/temida"
    assert env["pr"] == 88


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
