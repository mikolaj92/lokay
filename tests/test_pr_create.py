"""Issue-state guard for the PR creation atom."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

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
    def __init__(
        self,
        issue_state: str,
        *,
        pr_url: str = "",
        existing_prs: list[dict] | None = None,
    ) -> None:
        self.issue_state = issue_state
        self.pr_url = pr_url
        self.existing_prs = existing_prs or []
        self.calls: list[tuple[str, ...]] = []

    def run(self, spec: CommandSpec, *, live: bool) -> CommandResult:
        self.calls.append(tuple(spec.argv))
        stdout = ""
        if spec.argv[1:3] == ("issue", "view"):
            issue_number = int(spec.argv[3])
            stdout = json.dumps(
                {"number": issue_number, "state": self.issue_state}
            )
        return CommandResult(
            spec=spec, executed=live, returncode=0, stdout=stdout
        )

    def run_checked(self, spec: CommandSpec, *, live: bool) -> CommandResult:
        self.calls.append(tuple(spec.argv))
        stdout = (
            json.dumps([self.existing_prs])
            if spec.argv[1:2] == ("api",)
            else self.pr_url
        )
        return CommandResult(spec=spec, executed=live, returncode=0, stdout=stdout)


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


@pytest.mark.parametrize("repo", ["mikolaj92/Temida", "mikolaj92/takt"])
def test_product_repo_skips_without_gh_or_config(
    repo: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_if_called(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("product repositories must not call GitHub or load config")

    monkeypatch.setattr(pr_create, "load_cfg", fail_if_called)
    monkeypatch.setattr(pr_create, "mutations_allowed", fail_if_called)
    monkeypatch.setattr(pr_create, "runner", fail_if_called)
    monkeypatch.setattr(pr_create, "find_pr_fixing_issue", fail_if_called)
    monkeypatch.setattr(pr_create, "get_issue", fail_if_called)
    monkeypatch.setattr(pr_create, "create_pr", fail_if_called)
    args = _args(Path("unused.yaml"))
    args[args.index("--repo") + 1] = repo

    assert pr_create.main(args) == 0
    assert _envelope(capsys) == {
        "ok": True,
        "planned": False,
        "skipped": True,
        "reason": "repo_not_delivered_by_mini_mill",
        "repo": repo,
        "head": "ai/fix/239",
        "pr": None,
    }


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


def test_existing_pr_closing_issue_skips_create(tmp_path, monkeypatch, capsys):
    keywords = (
        "Close",
        "Closes",
        "Closed",
        "Fix",
        "Fixes",
        "Fixed",
        "Resolve",
        "Resolves",
        "Resolved",
    )
    states = (
        ("open", None),
        ("closed", "2025-01-01T12:00:00Z"),
    )
    for keyword in keywords:
        for state, merged_at in states:
            existing = {
                "number": 334,
                "state": state,
                "merged_at": merged_at,
                "body": f"Done\n\n{keyword} #239",
                "head": {"ref": "ai/fix/239"},
            }
            runner = _GhRunner("OPEN", existing_prs=[existing])
            monkeypatch.setattr(pr_create, "runner", lambda: runner)
            monkeypatch.setattr(
                pr_create, "mutations_allowed", lambda **kwargs: True
            )

            code = pr_create.main(_args(_cfg(tmp_path)))

            assert code == 0
            env = _envelope(capsys)
            assert env["ok"] is True
            assert env["existing"] is True
            assert env["pr"] == existing["number"]
            assert not any(
                call[1:3] == ("issue", "view") for call in runner.calls
            )
            assert not any(
                call[1:3] == ("pr", "create") for call in runner.calls
            )


def test_worktree_issue_overrides_stale_argument(
    tmp_path, monkeypatch, capsys
):
    runner = _GhRunner(
        "OPEN", pr_url="https://github.com/mikolaj92/lokay/pull/400\n"
    )
    monkeypatch.setattr(pr_create, "runner", lambda: runner)
    monkeypatch.setattr(pr_create, "mutations_allowed", lambda **kwargs: True)
    args = _args(_cfg(tmp_path))
    args[args.index("--issue") + 1] = "397"
    args[args.index("--body") + 1] = "Summary\n\nCloses #397"
    args[args.index("--head") + 1] = "ai/fix/399-harvest"

    code = pr_create.main(args)

    assert code == 0
    create_call = next(
        call for call in runner.calls if call[1:3] == ("pr", "create")
    )
    body = create_call[create_call.index("--body") + 1]
    assert "Closes #399" in body
    assert "Fixes #399" in body
    assert "#397" not in body
    issue_view = next(
        call for call in runner.calls if call[1:3] == ("issue", "view")
    )
    assert issue_view[3] == "399"


def test_created_pr_without_parseable_number_fails_closed(tmp_path, monkeypatch, capsys):
    runner = _GhRunner("OPEN", pr_url="created successfully\n")
    monkeypatch.setattr(pr_create, "runner", lambda: runner)
    monkeypatch.setattr(pr_create, "mutations_allowed", lambda **kwargs: True)

    assert pr_create.main(_args(_cfg(tmp_path))) == 1
    env = _envelope(capsys)
    assert env["ok"] is False
    assert "succeeded but number is unknown" in env["error"]
    source = Path(pr_create.__file__).parents[1] / "gh_prs.py"
    assert "PR creation success requires a recoverable delivery identity." in source.read_text()


def test_open_issue_creates_pr(tmp_path, monkeypatch, capsys):
    runner = _GhRunner(
        "OPEN",
        pr_url="https://github.com/mikolaj92/lokay/pull/239\n",
        existing_prs=[
            {
                "number": 334,
                "state": "open",
                "merged_at": None,
                "body": "References #239",
            }
        ],
    )
    monkeypatch.setattr(pr_create, "runner", lambda: runner)
    monkeypatch.setattr(pr_create, "mutations_allowed", lambda **kwargs: True)
    code = pr_create.main(_args(_cfg(tmp_path)))

    assert code == 0
    env = _envelope(capsys)
    assert env["ok"] is True
    assert env["pr"] == 239
    create_call = next(call for call in runner.calls if call[1:3] == ("pr", "create"))
    assert create_call[create_call.index("--body") + 1] == "body\nFixes #239"
