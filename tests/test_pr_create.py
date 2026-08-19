"""Issue-state guard for the PR creation atom."""

from __future__ import annotations

import json
from pathlib import Path

from lokay.proc import pr_create
from lokay.runner import CommandResult, CommandSpec


def _cfg(tmp_path: Path, *, mode: str = "live") -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(
        f"""
mode: {mode}
github:
  assignee: mill-bot
repos: []
""",
        encoding="utf-8",
    )
    return path


class _GhRunner:
    def __init__(self, issue_state: str, *, pr_url: str = "") -> None:
        self.issue_state = issue_state
        self.pr_url = pr_url
        self.calls: list[tuple[str, ...]] = []

    def run(self, spec: CommandSpec, *, live: bool) -> CommandResult:
        self.calls.append(tuple(spec.argv))
        stdout = ""
        if spec.argv[1:3] == ("issue", "view"):
            stdout = json.dumps({"number": 239, "state": self.issue_state})
        return CommandResult(
            spec=spec, executed=live, returncode=0, stdout=stdout
        )

    def run_checked(self, spec: CommandSpec, *, live: bool) -> CommandResult:
        self.calls.append(tuple(spec.argv))
        return CommandResult(
            spec=spec, executed=live, returncode=0, stdout=self.pr_url
        )


def _envelope(capsys) -> dict:
    return json.loads(capsys.readouterr().out.strip())


def _args(cfg: Path) -> list[str]:
    return [
        "--config",
        str(cfg),
        "--live",
        "--repo",
        "mikolaj92/lokay",
        "--issue",
        "239",
        "--title",
        "fix: skip closed issue",
        "--body",
        "body",
        "--head",
        "ai/fix/239",
    ]


def test_closed_issue_skips_create_pr(tmp_path, monkeypatch, capsys):
    runner = _GhRunner("CLOSED")
    monkeypatch.setattr(pr_create, "runner", lambda: runner)
    monkeypatch.setattr(pr_create, "mutations_allowed", lambda **kwargs: True)

    def fail_create_pr(*args, **kwargs):
        raise AssertionError("create_pr must not run for a closed issue")

    monkeypatch.setattr(pr_create, "create_pr", fail_create_pr)
    code = pr_create.main(_args(_cfg(tmp_path)))

    assert code == 1
    env = _envelope(capsys)
    assert env["ok"] is False
    assert env["reason"] == "issue_closed"
    assert env["issue_state"] == "CLOSED"
    assert any(call[1:3] == ("issue", "view") for call in runner.calls)
    assert not any(call[1:3] == ("pr", "create") for call in runner.calls)


def test_open_issue_creates_pr(tmp_path, monkeypatch, capsys):
    runner = _GhRunner(
        "OPEN", pr_url="https://github.com/mikolaj92/lokay/pull/239\n"
    )
    monkeypatch.setattr(pr_create, "runner", lambda: runner)
    monkeypatch.setattr(pr_create, "mutations_allowed", lambda **kwargs: True)
    code = pr_create.main(_args(_cfg(tmp_path)))

    assert code == 0
    env = _envelope(capsys)
    assert env["ok"] is True
    assert env["pr"] == 239
    assert any(call[1:3] == ("pr", "create") for call in runner.calls)
