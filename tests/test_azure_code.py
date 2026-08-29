"""Azure Repos code plugin: path + merge-commit from one target. No network."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pytest

from lokay.azure_boards import AzureLoginError, recorded_path
from lokay.catalog import CatalogBinding
from lokay.code import (
    AzureCode,
    CodeError,
    CodeSlot,
    CodeTarget,
    bind_code,
    load_code,
    parse_code_slot,
    slot_from_repo,
)
from lokay.code.catalog import KNOWN_CODE_PLUGINS
from lokay.config import Config, RepoConfig
from lokay.runner import CommandResult, CommandSpec


def _pr(
    number: int,
    *,
    title: str = "",
    description: str = "",
    status: str = "active",
    head: str = "ai/fix/7-parser",
    commit: str = "abc123",
    comments: list[str] | None = None,
    checks: list[str] | None = None,
) -> dict[str, Any]:
    ref = head if str(head).startswith("refs/") else f"refs/heads/{head}"
    return {
        "pullRequestId": number,
        "title": title,
        "description": description,
        "status": status,
        "sourceRefName": ref,
        "targetRefName": "refs/heads/main",
        "createdBy": {"uniqueName": "ada"},
        "url": f"https://dev.azure.com/contoso/app/_git/repo/pullrequest/{number}",
        "isDraft": False,
        "mergeStatus": "succeeded",
        "lastMergeSourceCommit": {"commitId": commit},
        "_comments": list(comments or []),
        "_checks": list(checks or ["succeeded"]),
    }


class RecordedAzureRepos:
    """Recorded Azure Repos REST. No sockets."""

    def __init__(self, items: list[dict[str, Any]]) -> None:
        self.items = {int(row["pullRequestId"]): dict(row) for row in items}
        self.calls: list[tuple[str, str, Any]] = []

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        body: bytes | None,
    ) -> tuple[int, Any]:
        parsed = urlparse(url)
        path = parsed.path
        payload = json.loads(body.decode("utf-8")) if body else None
        self.calls.append((method, recorded_path(url), payload))
        if "Authorization" not in headers:
            return 401, {"message": "no login"}

        number = _pull_id(path)
        if method == "GET" and path.rstrip("/").endswith("/pullrequests") and number is None:
            open_rows = [
                self._public(item)
                for item in self.items.values()
                if str(item.get("status") or "") == "active"
            ]
            return 200, {"value": open_rows}

        if number is None:
            return 404, {"message": "not a pull request"}

        if method == "GET" and path.endswith("/threads"):
            item = self.items.get(number)
            if item is None:
                return 404, {"message": "not found"}
            return 200, {
                "value": [
                    {"comments": [{"content": text}]}
                    for text in item.get("_comments") or []
                ]
            }

        if method == "POST" and path.endswith("/threads"):
            item = self.items.get(number)
            if item is None:
                return 404, {"message": "not found"}
            comments = list((payload or {}).get("comments") or [])
            text = ""
            if comments and isinstance(comments[0], dict):
                text = str(comments[0].get("content") or "")
            item.setdefault("_comments", []).append(text)
            return 200, {"comments": [{"content": text}]}

        if method == "GET" and path.endswith("/statuses"):
            item = self.items.get(number)
            if item is None:
                return 404, {"message": "not found"}
            return 200, {
                "value": [{"state": state} for state in item.get("_checks") or []]
            }

        if method == "GET":
            item = self.items.get(number)
            if item is None:
                return 404, {"message": "not found"}
            return 200, self._public(number)

        if method == "PATCH":
            item = self.items.get(number)
            if item is None:
                return 404, {"message": "not found"}
            options = (payload or {}).get("completionOptions") or {}
            if options.get("mergeStrategy") == "squash":
                raise AssertionError("merge-commit must not squash")
            if (payload or {}).get("status") == "completed":
                item["status"] = "completed"
            if (payload or {}).get("status") == "abandoned":
                item["status"] = "abandoned"
            return 200, self._public(number)

        return 404, {"message": f"unrecorded {method} {path}"}

    def _public(self, item: dict[str, Any] | int) -> dict[str, Any]:
        row = self.items[item] if isinstance(item, int) else item
        return {
            key: value
            for key, value in row.items()
            if not str(key).startswith("_")
        }


def _pull_id(path: str) -> int | None:
    parts = [part for part in path.split("/") if part]
    for index, part in enumerate(parts):
        if part.lower() == "pullrequests" and index + 1 < len(parts):
            token = parts[index + 1]
            if token.isdigit():
                return int(token)
    return None


class _Runner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.clone_rc = 0

    def run(self, spec: CommandSpec, *, live: bool) -> CommandResult:
        self.calls.append(spec.argv)
        argv = spec.argv
        if len(argv) >= 2 and argv[0] == "git" and argv[1] == "clone" and self.clone_rc == 0:
            Path(argv[-1]).mkdir(parents=True, exist_ok=True)
        return CommandResult(
            spec=spec, executed=live, returncode=self.clone_rc, stdout="", stderr=""
        )

    def run_checked(self, spec: CommandSpec, *, live: bool) -> CommandResult:
        result = self.run(spec, live=live)
        if live and result.returncode != 0:
            raise RuntimeError(f"command failed ({result.returncode}): {spec.display()}")
        return result


def _cfg(
    tmp_path: Path,
    *,
    plugin: str = "azure",
    target: str = "contoso/app/repo",
) -> Config:
    clone = tmp_path / "repo"
    return Config(
        mode="live",
        branch_prefix="ai/fix",
        merge_enabled=True,
        gh_survey_pace_ms=0,
        worktrees_root=tmp_path / "worktrees",
        repos=[
            RepoConfig(
                name=target,
                clone_path=clone,
                issues=CatalogBinding("jira", "PROJ"),
                code=CatalogBinding(plugin, target),
            )
        ],
    )


def _host(
    tmp_path: Path,
    runner: _Runner,
    cfg: Config,
    transport: RecordedAzureRepos,
    *,
    token: str = "recorded",
) -> AzureCode:
    slot = slot_from_repo(cfg.repos[0])
    return AzureCode.from_slot(
        slot,
        runner=runner,
        config=cfg,
        live=True,
        env={"AZURE_DEVOPS_PAT": token},
        transport=transport,
    )


def test_azure_is_a_known_code_plugin() -> None:
    assert "azure" in KNOWN_CODE_PLUGINS
    assert "github" in KNOWN_CODE_PLUGINS


def test_catalog_code_plugin_azure_loads_this_plugin(tmp_path: Path) -> None:
    slot = parse_code_slot(
        {
            "issues": {"plugin": "jira", "target": "PROJ"},
            "code": {
                "plugin": "azure",
                "target": "contoso/app/repo",
                "clone_path": str(tmp_path / "repo"),
            },
        },
        default_name="ignored",
        default_clone=tmp_path / "ignored",
    )
    assert slot == CodeSlot(
        plugin="azure",
        target="contoso/app/repo",
        clone_path=tmp_path / "repo",
    )
    assert slot.plugin != "jira"


def test_azure_code_does_not_read_issues_plugin(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    assert cfg.repos[0].issues.plugin == "jira"
    slot = slot_from_repo(cfg.repos[0])
    assert slot.plugin == "azure"
    assert slot.target == "contoso/app/repo"
    runner = _Runner()
    transport = RecordedAzureRepos([_pr(7, title="fix parser")])
    contract = load_code(
        slot,
        runner=runner,
        config=cfg,
        live=True,
        env={"AZURE_DEVOPS_PAT": "recorded"},
        transport=transport,
    )
    assert isinstance(contract.repo.target, type(contract.target))
    assert contract.target == CodeTarget(plugin="azure", id="contoso/app/repo")
    assert contract.repo.target == contract.pr.target == contract.target


def test_azure_plugin_path_and_merge_commit_from_one_target(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    runner = _Runner()
    transport = RecordedAzureRepos([_pr(7, title="fix parser", description="Closes #874")])
    host = _host(tmp_path, runner, cfg, transport)
    contract = bind_code(host.target, repo=host.repo, pr=host.pr)
    assert contract.target.plugin == "azure"
    assert contract.repo.target == contract.pr.target == contract.target
    assert contract.target.id == "contoso/app/repo"
    assert contract.repo.path() == tmp_path / "repo"

    cloned = contract.repo.clone()
    assert cloned == tmp_path / "repo"
    assert cloned.is_dir()
    clone_calls = [argv for argv in runner.calls if argv[:2] == ("git", "clone")]
    assert clone_calls
    assert "contoso/app/_git/repo" in clone_calls[0][2]
    assert str(tmp_path / "repo") in clone_calls[0]
    assert all("recorded" not in part for argv in clone_calls for part in argv)

    head = contract.repo.branch("ai/fix/7-parser")
    assert head == "ai/fix/7-parser"

    rows = contract.pr.list_open()
    assert [row.number for row in rows] == [7]
    assert rows[0].head == "ai/fix/7-parser"
    assert rows[0].target == host.target

    merged = contract.pr.merge_commit(7)
    assert merged.state == "merged"
    assert merged.merge_method == "merge"
    assert merged.merge_method != "squash"
    patches = [payload for method, _, payload in transport.calls if method == "PATCH"]
    assert patches
    assert patches[0]["status"] == "completed"
    assert patches[0]["completionOptions"]["mergeStrategy"] == "noFastForward"
    assert patches[0]["completionOptions"]["mergeStrategy"] != "squash"


def test_load_code_from_catalog_field(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    runner = _Runner()
    transport = RecordedAzureRepos([_pr(7, title="fix parser")])
    contract = load_code(
        slot_from_repo(cfg.repos[0]),
        runner=runner,
        config=cfg,
        live=True,
        env={"AZURE_DEVOPS_PAT": "recorded"},
        transport=transport,
    )
    assert contract.target == CodeTarget(plugin="azure", id="contoso/app/repo")
    contract.repo.clone()
    contract.pr.merge_commit(7)
    assert any(argv[:2] == ("git", "clone") for argv in runner.calls)
    assert any(method == "PATCH" for method, _, _ in transport.calls)


def test_azure_host_has_no_tasks(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    host = _host(tmp_path, _Runner(), cfg, RecordedAzureRepos([]))
    for name in (
        "list_issues",
        "get_issue",
        "list_tasks",
        "comment_issue",
        "mark_issue",
        "close_issue",
        "tasks",
        "issues",
    ):
        assert not hasattr(host, name)
        assert not hasattr(host.repo, name)
        assert not hasattr(host.pr, name)
    contract = bind_code(host.target, repo=host.repo, pr=host.pr)
    assert not hasattr(contract, "tasks")
    assert not hasattr(contract, "issues")


def test_azure_pr_list_get_checks_comment_close(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    transport = RecordedAzureRepos(
        [_pr(7, title="fix parser", comments=["looks good"], checks=["succeeded"])]
    )
    host = _host(tmp_path, _Runner(), cfg, transport)
    contract = bind_code(host.target, repo=host.repo, pr=host.pr)
    rows = contract.pr.list_open()
    assert rows[0].number == 7
    one = contract.pr.get(7)
    assert one.title == "fix parser"
    assert one.target == host.target
    assert "looks good" in one.comments
    checks = contract.pr.checks(7)
    assert checks.status == "passed"
    assert checks.green is True
    noted = contract.pr.comment(7, "ship it")
    assert "ship it" in noted.comments
    closed = contract.pr.close(7)
    assert closed.state == "closed"
    assert closed.merge_method is None


def test_no_login_says_so_and_does_not_fake_success(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    slot = slot_from_repo(cfg.repos[0])
    with pytest.raises(AzureLoginError, match="no login"):
        AzureCode.from_slot(slot, runner=_Runner(), config=cfg, live=True, env={})
    with pytest.raises(AzureLoginError, match="no login"):
        load_code(slot, runner=_Runner(), config=cfg, live=True, env={})
    host = AzureCode(
        CodeTarget(plugin="azure", id="contoso/app/repo"),
        clone_path=tmp_path / "repo",
        runner=_Runner(),
        config=cfg,
        live=True,
        token="",
        transport=RecordedAzureRepos([_pr(1, title="hidden")]),
    )
    with pytest.raises(AzureLoginError, match="no login"):
        host.repo.clone()
    with pytest.raises(AzureLoginError, match="no login"):
        host.pr.list_open()
    with pytest.raises(AzureLoginError, match="no login"):
        host.pr.get(1)
    with pytest.raises(AzureLoginError, match="no login"):
        host.pr.comment(1, "x")
    with pytest.raises(AzureLoginError, match="no login"):
        host.pr.merge_commit(1)
    with pytest.raises(AzureLoginError, match="no login"):
        host.pr.close(1)


def test_split_target_rejects_boards_org_project() -> None:
    from lokay.code.azure import split_repo_target

    with pytest.raises(CodeError, match="org/project/repo"):
        split_repo_target("contoso/app")
    with pytest.raises(CodeError, match="org/project/repo"):
        split_repo_target("contoso")
    assert split_repo_target("contoso/app/repo") == ("contoso", "app", "repo")


def test_worktree_path_stays_on_the_same_target(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    host = AzureCode(
        CodeTarget(plugin="azure", id="contoso/app/repo"),
        clone_path=tmp_path / "repo",
        runner=_Runner(),
        config=cfg,
        live=False,
        token="recorded",
        transport=RecordedAzureRepos([]),
    )
    wt = host.repo.worktree("ai/fix/7-parser")
    assert "contoso__app__repo" in str(wt)
    assert wt != host.repo.path()
