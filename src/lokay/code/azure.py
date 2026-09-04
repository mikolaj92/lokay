"""Azure Repos code plugin. One executor: clone/branch/worktree and PR sieve.

Same target (org/project/repo). Login from the process environment.
Zero work items. No gh. No issues.plugin.
"""

from __future__ import annotations

import base64
import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import quote, urlencode

from lokay.azure_boards import AzureLoginError, UrlLibTransport, read_azure_token
from lokay.code.catalog import CodeSlot
from lokay.code.contract import CodeError, CodeTarget
from lokay.code.pr import Change, ChangeChecks
from lokay.config import Config, RepoConfig
from lokay.git_worktree import ensure_worktree, worktree_dir
from lokay.runner import CommandSpec, Runner

API_VERSION = "7.1"
PLUGIN = "azure"
_HEADS = "refs/heads/"
_FAILED = frozenset({"failed", "error"})
_PENDING = frozenset({"pending", "notset", "not_set"})
_PASSED = frozenset({"succeeded", "notapplicable", "not_applicable"})

__all__ = ("AzureCode", "AzurePr", "AzureRepo", "split_repo_target")


def split_repo_target(target: str) -> tuple[str, str, str]:
    """org/project/repo. Boards is org/project; this plugin needs the repo."""
    raw = str(target or "").strip().strip("/")
    parts = [part.strip() for part in raw.split("/") if part.strip()]
    if len(parts) != 3:
        raise CodeError("azure code target must be org/project/repo")
    return parts[0], parts[1], parts[2]


def _need_name(name: str, *, what: str) -> str:
    text = str(name or "").strip()
    if not text:
        raise CodeError(f"{what} name must be non-empty")
    return text


def _basic_blob(token: str) -> str:
    return base64.b64encode(f":{token}".encode("ascii")).decode("ascii")


def _head_name(ref: str) -> str:
    text = str(ref or "").strip()
    if text.startswith(_HEADS):
        return text[len(_HEADS) :]
    return text


def _state(status: str) -> str:
    token = str(status or "").strip().lower()
    if token == "completed":
        return "merged"
    if token == "abandoned":
        return "closed"
    return "open"


def _repo_cfg(target: CodeTarget, clone_path: Path) -> RepoConfig:
    return RepoConfig(name=target.id, clone_path=Path(clone_path))


class _GitClient:
    """Azure Repos git/PR REST. Tests inject a recorded transport."""

    def __init__(
        self,
        *,
        organization: str,
        project: str,
        repository: str,
        token: str,
        transport: Any | None = None,
        base_url: str = "https://dev.azure.com",
    ) -> None:
        self.organization = organization
        self.project = project
        self.repository = repository
        self._token = token
        self._transport = transport or UrlLibTransport()
        self._base = str(base_url).rstrip("/")

    def _require_login(self) -> None:
        if not str(self._token or "").strip():
            raise AzureLoginError()

    def _url(self, path: str, *, params: dict[str, str]) -> str:
        org = quote(self.organization, safe="")
        project = quote(self.project, safe="")
        return f"{self._base}/{org}/{project}/{path.lstrip('/')}?{urlencode(params)}"

    def _repo_path(self, suffix: str) -> str:
        repo = quote(self.repository, safe="")
        return f"_apis/git/repositories/{repo}/{suffix.lstrip('/')}"

    def call(
        self,
        method: str,
        suffix: str,
        *,
        params: dict[str, str] | None = None,
        payload: Any = None,
    ) -> tuple[int, Any]:
        self._require_login()
        query = {"api-version": API_VERSION}
        query.update(params or {})
        headers = {
            "Accept": "application/json",
            "Authorization": f"Basic {_basic_blob(self._token)}",
        }
        body: bytes | None = None
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        return self._transport.request(
            method, self._url(self._repo_path(suffix), params=query), headers=headers, body=body
        )

    def raise_for(self, status: int, payload: Any, *, action: str) -> None:
        detail = payload if isinstance(payload, str) else json.dumps(payload or {})
        raise CodeError(f"azure {action} failed ({status}): {detail}")


class AzureRepo:
    """Repo block: path, clone, branch, worktree. Today's git clone + worktree."""

    def __init__(
        self,
        target: CodeTarget,
        *,
        clone_path: Path,
        runner: Runner,
        config: Config,
        live: bool,
        token: str,
        organization: str,
        project: str,
        repository: str,
        base_url: str = "https://dev.azure.com",
    ) -> None:
        self.target = target
        self._root = Path(clone_path)
        self._runner = runner
        self._config = config
        self._live = live
        self._token = token
        self._org = organization
        self._project = project
        self._repository = repository
        self._base = str(base_url).rstrip("/")
        self._row = _repo_cfg(target, self._root)

    def path(self) -> Path:
        return self._root

    def clone_url(self) -> str:
        org = quote(self._org, safe="")
        project = quote(self._project, safe="")
        repo = quote(self._repository, safe="")
        return f"{self._base}/{org}/{project}/_git/{repo}"

    def _require_login(self) -> None:
        if not str(self._token or "").strip():
            raise AzureLoginError()

    def _auth_env(self) -> dict[str, str]:
        self._require_login()
        return {
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "http.extraheader",
            "GIT_CONFIG_VALUE_0": f"AUTHORIZATION: Basic {_basic_blob(self._token)}",
        }

    def clone(self) -> Path:
        if self._root.exists():
            return self._root
        self._require_login()
        if not self._live:
            return self._root
        self._root.parent.mkdir(parents=True, exist_ok=True)
        spec = CommandSpec(
            argv=("git", "clone", self.clone_url(), str(self._root)),
            env=self._auth_env(),
            timeout_seconds=600,
        )
        result = self._runner.run(spec, live=True)
        if result.returncode != 0:
            detail = ((result.stderr or "") + "\n" + (result.stdout or "")).strip()
            raise CodeError(detail or f"clone {self.target.id} failed")
        return self._root

    def branch(self, name: str) -> str:
        head = _need_name(name, what="branch")
        self.clone()
        return head

    def worktree(self, name: str, *, base: str = "main", reset_to_base: bool = False) -> Path:
        head = _need_name(name, what="worktree")
        if not self._live:
            return worktree_dir(self._config, self._row, head)
        self.clone()
        return ensure_worktree(
            self._runner,
            self._config,
            self._row,
            head,
            live=True,
            base=base,
            reset_to_base=reset_to_base,
        )


class AzurePr:
    """PR sieve: list, get, checks, comment, merge-commit, close. No tasks."""

    def __init__(
        self,
        target: CodeTarget,
        *,
        token: str,
        transport: Any | None,
        organization: str,
        project: str,
        repository: str,
        live: bool,
        base_url: str = "https://dev.azure.com",
    ) -> None:
        self.target = target
        self._live = live
        self._client = _GitClient(
            organization=organization,
            project=project,
            repository=repository,
            token=token,
            transport=transport,
            base_url=base_url,
        )
        self._listed: dict[int, Change] = {}
        self._lokay: list[dict[str, Any]] = []

    def lokay_dicts(self) -> list[dict[str, Any]]:
        """Envelope rows for today's list_prs atom."""
        return [dict(row) for row in self._lokay]

    def _payload_change(
        self,
        payload: dict[str, Any],
        *,
        comments: tuple[str, ...] = (),
        checks_status: str = "none",
    ) -> Change:
        number = int(payload.get("pullRequestId") or payload.get("id") or 0)
        return Change(
            target=self.target,
            number=number,
            title=str(payload.get("title") or ""),
            body=str(payload.get("description") or ""),
            head=_head_name(str(payload.get("sourceRefName") or "")),
            state=_state(str(payload.get("status") or "active")),
            comments=comments,
            checks_status=checks_status,
        )

    def _lokay_row(self, payload: dict[str, Any], change: Change) -> dict[str, Any]:
        created = payload.get("createdBy")
        author = ""
        if isinstance(created, dict):
            author = str(created.get("uniqueName") or created.get("displayName") or "")
        sha = ""
        source = payload.get("lastMergeSourceCommit")
        if isinstance(source, dict):
            sha = str(source.get("commitId") or "")
        return {
            "repo": self.target.id,
            "number": change.number,
            "title": change.title,
            "body": change.body,
            "head_ref": change.head,
            "head_sha": sha,
            "author": author,
            "url": str(payload.get("url") or ""),
            "is_draft": bool(payload.get("isDraft")),
            "mergeable": payload.get("mergeStatus"),
            "labels": [],
        }

    def _comments(self, number: int) -> tuple[str, ...]:
        status, payload = self._client.call("GET", f"pullrequests/{int(number)}/threads")
        if status == 404:
            return ()
        if status >= 400:
            self._client.raise_for(status, payload, action="threads")
        out: list[str] = []
        for thread in list((payload or {}).get("value") or []):
            if not isinstance(thread, dict):
                continue
            for row in list(thread.get("comments") or []):
                if not isinstance(row, dict):
                    continue
                text = str(row.get("content") or "").strip()
                if text:
                    out.append(text)
        return tuple(out)

    def _load(self, payload: dict[str, Any], *, with_comments: bool) -> Change:
        comments = self._comments(int(payload.get("pullRequestId") or 0)) if with_comments else ()
        return self._payload_change(payload, comments=comments)

    def list_open(self) -> list[Change]:
        if not self._live:
            return [row for row in self._listed.values() if row.state == "open"]
        status, payload = self._client.call(
            "GET",
            "pullrequests",
            params={"searchCriteria.status": "active"},
        )
        if status >= 400:
            self._client.raise_for(status, payload, action="list")
        rows: list[Change] = []
        lokay: list[dict[str, Any]] = []
        listed: dict[int, Change] = {}
        for raw in list((payload or {}).get("value") or []):
            if not isinstance(raw, dict):
                continue
            change = self._payload_change(raw)
            if change.number < 1 or change.state != "open":
                continue
            listed[change.number] = change
            rows.append(change)
            lokay.append(self._lokay_row(raw, change))
        self._listed = listed
        self._lokay = lokay
        return rows

    def get(self, number: int) -> Change:
        if not self._live:
            row = self._listed.get(int(number))
            if row is not None:
                return row
            raise CodeError(f"change {number} not on {self.target}")
        status, payload = self._client.call("GET", f"pullrequests/{int(number)}")
        if status == 404 or not isinstance(payload, dict) or not (
            payload.get("pullRequestId") or payload.get("id")
        ):
            row = self._listed.get(int(number))
            if row is not None:
                return row
            raise CodeError(f"change {number} not on {self.target}")
        if status >= 400:
            self._client.raise_for(status, payload, action="get")
        return self._load(payload, with_comments=True)

    def checks(self, number: int) -> ChangeChecks:
        if not self._live:
            row = self._listed.get(int(number))
            status = row.checks_status if row is not None else "none"
            return ChangeChecks(status=status, green=status == "passed")
        status, payload = self._client.call("GET", f"pullrequests/{int(number)}/statuses")
        if status == 404:
            return ChangeChecks(status="none", green=False)
        if status >= 400:
            self._client.raise_for(status, payload, action="checks")
        states = [
            str(row.get("state") or "").strip().lower()
            for row in list((payload or {}).get("value") or [])
            if isinstance(row, dict)
        ]
        if not states:
            return ChangeChecks(status="none", green=False)
        if any(item in _FAILED for item in states):
            return ChangeChecks(status="failed", green=False)
        if any(item in _PENDING for item in states):
            return ChangeChecks(status="pending", green=False)
        if all(item in _PASSED for item in states):
            return ChangeChecks(status="passed", green=True)
        return ChangeChecks(status="pending", green=False)

    def comment(self, number: int, body: str) -> Change:
        text = str(body or "").strip()
        if not text:
            raise CodeError("comment body must be non-empty")
        if self._live:
            status, payload = self._client.call(
                "POST",
                f"pullrequests/{int(number)}/threads",
                payload={
                    "comments": [
                        {"parentCommentId": 0, "content": text, "commentType": "text"}
                    ],
                    "status": "active",
                },
            )
            if status == 404:
                raise CodeError(f"change {number} not on {self.target}")
            if status >= 400:
                self._client.raise_for(status, payload, action="comment")
        try:
            row = self.get(int(number))
        except CodeError:
            row = Change(
                target=self.target,
                number=int(number),
                title="",
                body="",
                head="",
                state="open",
                comments=(text,),
            )
        if text not in row.comments:
            return replace(row, comments=row.comments + (text,))
        return row

    def _source_commit(self, number: int) -> str:
        status, payload = self._client.call("GET", f"pullrequests/{int(number)}")
        if status >= 400 or not isinstance(payload, dict):
            self._client.raise_for(status if status >= 400 else 500, payload, action="merge")
        source = payload.get("lastMergeSourceCommit")
        commit = ""
        if isinstance(source, dict):
            commit = str(source.get("commitId") or "").strip()
        if not commit:
            raise CodeError(f"change {number} has no merge source commit")
        return commit

    def merge_commit(self, number: int) -> Change:
        if self._live:
            commit = self._source_commit(int(number))
            status, payload = self._client.call(
                "PATCH",
                f"pullrequests/{int(number)}",
                payload={
                    "status": "completed",
                    "lastMergeSourceCommit": {"commitId": commit},
                    "completionOptions": {
                        "mergeStrategy": "noFastForward",
                        "deleteSourceBranch": False,
                    },
                },
            )
            if status == 404:
                raise CodeError(f"change {number} not on {self.target}")
            if status >= 400:
                self._client.raise_for(status, payload, action="merge")
        try:
            row = self.get(int(number))
        except CodeError:
            row = Change(
                target=self.target,
                number=int(number),
                title="",
                body="",
                head="",
                state="open",
            )
        if not self._live:
            return replace(row, merge_method="merge")
        return replace(row, state="merged", merge_method="merge")

    def close(self, number: int, comment: str = "") -> Change:
        text = str(comment or "").strip()
        if text:
            self.comment(int(number), text)
        if self._live:
            status, payload = self._client.call(
                "PATCH",
                f"pullrequests/{int(number)}",
                payload={"status": "abandoned"},
            )
            if status == 404:
                raise CodeError(f"change {number} not on {self.target}")
            if status >= 400:
                self._client.raise_for(status, payload, action="close")
        try:
            row = self.get(int(number))
        except CodeError:
            row = Change(
                target=self.target,
                number=int(number),
                title="",
                body="",
                head="",
                state="open",
            )
        if not self._live:
            return row
        return replace(row, state="closed")


class AzureCode:
    """One Azure Repos host. Repo and PR share this target. No task list."""

    def __init__(
        self,
        target: CodeTarget,
        *,
        clone_path: Path,
        runner: Runner,
        config: Config,
        live: bool,
        token: str,
        transport: Any | None = None,
        base_url: str = "https://dev.azure.com",
    ) -> None:
        if target.plugin != PLUGIN:
            raise CodeError(f"azure plugin cannot bind {target}")
        organization, project, repository = split_repo_target(target.id)
        self.target = target
        self.repo = AzureRepo(
            target,
            clone_path=clone_path,
            runner=runner,
            config=config,
            live=live,
            token=token,
            organization=organization,
            project=project,
            repository=repository,
            base_url=base_url,
        )
        self.pr = AzurePr(
            target,
            token=token,
            transport=transport,
            organization=organization,
            project=project,
            repository=repository,
            live=live,
            base_url=base_url,
        )

    @classmethod
    def from_slot(
        cls,
        slot: CodeSlot,
        *,
        runner: Runner,
        config: Config,
        live: bool,
        env: Mapping[str, str] | None = None,
        transport: Any | None = None,
        base_url: str = "https://dev.azure.com",
    ) -> AzureCode:
        if slot.plugin != PLUGIN:
            raise CodeError(f"unknown code plugin: {slot.plugin}")
        token = read_azure_token(env)
        if not token:
            raise AzureLoginError()
        return cls(
            CodeTarget(plugin=PLUGIN, id=slot.target),
            clone_path=slot.clone_path,
            runner=runner,
            config=config,
            live=live,
            token=token,
            transport=transport,
            base_url=base_url,
        )
