"""Thin Azure Boards work-item client. No PR, repo, clone, or merge."""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

API_VERSION = "7.1"
COMMENTS_API_VERSION = "7.1-preview.4"
CLOSED_STATES = frozenset({"closed", "done", "removed", "completed"})
TOKEN_ENV = (
    "AZURE_DEVOPS_PAT",
    "AZURE_DEVOPS_EXT_PAT",
    "SYSTEM_ACCESSTOKEN",
)
NO_LOGIN = "azure: no login (set AZURE_DEVOPS_PAT)"


class AzureLoginError(RuntimeError):
    """Process environment has no Azure Boards secret."""

    def __init__(self) -> None:
        super().__init__(NO_LOGIN)


class Transport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        body: bytes | None,
    ) -> tuple[int, Any]: ...


def split_target(target: str) -> tuple[str, str]:
    raw = str(target or "").strip()
    org, sep, project = raw.partition("/")
    org, project = org.strip(), project.strip()
    if not sep or not org or not project:
        raise ValueError("azure target must be org/project")
    return org, project


def read_azure_token(env: Mapping[str, str] | None = None) -> str:
    source = env if env is not None else os.environ
    for name in TOKEN_ENV:
        token = str(source.get(name) or "").strip()
        if token:
            return token
    return ""


def is_closed_state(state: str) -> bool:
    return str(state or "").strip().lower() in CLOSED_STATES


def _identity_name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("uniqueName") or value.get("displayName") or "").strip()
    return str(value or "").strip()


def _tags(raw: Any) -> list[str]:
    return [part.strip() for part in str(raw or "").split(";") if part.strip()]


def _basic_auth(token: str) -> str:
    blob = base64.b64encode(f":{token}".encode("ascii")).decode("ascii")
    return f"Basic {blob}"


@dataclass
class WorkItem:
    id: int
    title: str = ""
    description: str = ""
    state: str = "Active"
    tags: list[str] = field(default_factory=list)
    assignees: list[str] = field(default_factory=list)
    author: str = ""
    comments: list[str] = field(default_factory=list)
    rev: int = 1

    @property
    def closed(self) -> bool:
        return is_closed_state(self.state)


def work_item_from_payload(payload: dict[str, Any], *, comments: list[str] | None = None) -> WorkItem:
    fields = dict(payload.get("fields") or {})
    assigned = _identity_name(fields.get("System.AssignedTo"))
    return WorkItem(
        id=int(payload.get("id") or fields.get("System.Id") or 0),
        title=str(fields.get("System.Title") or ""),
        description=str(fields.get("System.Description") or ""),
        state=str(fields.get("System.State") or "Active"),
        tags=_tags(fields.get("System.Tags")),
        assignees=[assigned] if assigned else [],
        author=_identity_name(fields.get("System.CreatedBy")),
        comments=list(comments or []),
        rev=int(payload.get("rev") or 1),
    )


class UrlLibTransport:
    """stdlib HTTP. Tests inject a recorded transport instead."""

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        body: bytes | None,
    ) -> tuple[int, Any]:
        req = Request(url, data=body, method=method, headers=headers)
        try:
            with urlopen(req, timeout=30) as resp:
                raw = resp.read()
                status = int(resp.status)
        except HTTPError as exc:
            raw = exc.read()
            status = int(exc.code)
        except URLError as exc:
            raise RuntimeError(f"azure transport failed: {exc}") from exc
        if not raw:
            return status, None
        return status, json.loads(raw.decode("utf-8"))


class AzureBoardsClient:
    """Work items only. Parent never calls this; AzureTasks does."""

    def __init__(
        self,
        *,
        organization: str,
        project: str,
        token: str,
        transport: Transport | None = None,
        base_url: str = "https://dev.azure.com",
    ) -> None:
        self.organization = organization
        self.project = project
        self._token = token
        self._transport = transport or UrlLibTransport()
        self._base = str(base_url).rstrip("/")

    @classmethod
    def from_env(
        cls,
        *,
        target: str,
        env: Mapping[str, str] | None = None,
        transport: Transport | None = None,
        base_url: str = "https://dev.azure.com",
    ) -> AzureBoardsClient:
        org, project = split_target(target)
        token = read_azure_token(env)
        if not token:
            raise AzureLoginError()
        return cls(
            organization=org,
            project=project,
            token=token,
            transport=transport,
            base_url=base_url,
        )

    def _require_login(self) -> None:
        if not str(self._token or "").strip():
            raise AzureLoginError()

    def _url(self, path: str, *, params: dict[str, str]) -> str:
        org = quote(self.organization, safe="")
        project = quote(self.project, safe="")
        return f"{self._base}/{org}/{project}/{path.lstrip('/')}?{urlencode(params)}"

    def _call(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str],
        payload: Any = None,
        content_type: str = "application/json",
    ) -> tuple[int, Any]:
        self._require_login()
        headers = {
            "Accept": "application/json",
            "Authorization": _basic_auth(self._token),
        }
        body: bytes | None = None
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = content_type
        return self._transport.request(
            method, self._url(path, params=params), headers=headers, body=body
        )

    def _raise(self, status: int, payload: Any, *, action: str) -> None:
        detail = payload if isinstance(payload, str) else json.dumps(payload or {})
        raise RuntimeError(f"azure {action} failed ({status}): {detail}")

    def _comments(self, number: int) -> list[str]:
        status, payload = self._call(
            "GET",
            f"_apis/wit/workItems/{int(number)}/comments",
            params={"api-version": COMMENTS_API_VERSION},
        )
        if status == 404:
            return []
        if status >= 400:
            self._raise(status, payload, action="comments")
        rows = list((payload or {}).get("comments") or [])
        out: list[str] = []
        for row in rows:
            if isinstance(row, dict):
                text = str(row.get("text") or "")
            else:
                text = str(row or "")
            if text:
                out.append(text)
        return out

    def _load(self, payload: dict[str, Any], *, with_comments: bool) -> WorkItem:
        comments = self._comments(int(payload.get("id") or 0)) if with_comments else []
        return work_item_from_payload(payload, comments=comments)

    def list_open(self) -> list[WorkItem]:
        escaped = self.project.replace("'", "''")
        query = (
            "SELECT [System.Id] FROM WorkItems "
            f"WHERE [System.TeamProject] = '{escaped}' "
            "AND [System.State] <> 'Closed' "
            "AND [System.State] <> 'Done' "
            "AND [System.State] <> 'Removed' "
            "AND [System.State] <> 'Completed' "
            "ORDER BY [System.Id]"
        )
        status, payload = self._call(
            "POST",
            "_apis/wit/wiql",
            params={"api-version": API_VERSION},
            payload={"query": query},
        )
        if status >= 400:
            self._raise(status, payload, action="list")
        ids = [
            int(row["id"])
            for row in list((payload or {}).get("workItems") or [])
            if isinstance(row, dict) and row.get("id")
        ]
        if not ids:
            return []
        status, batch = self._call(
            "GET",
            "_apis/wit/workitems",
            params={
                "ids": ",".join(str(n) for n in ids),
                "$expand": "all",
                "api-version": API_VERSION,
            },
        )
        if status >= 400:
            self._raise(status, batch, action="list")
        items: list[WorkItem] = []
        for row in list((batch or {}).get("value") or []):
            if not isinstance(row, dict):
                continue
            item = self._load(row, with_comments=False)
            if item.id >= 1 and not item.closed:
                items.append(item)
        return items

    def get(self, number: int) -> WorkItem | None:
        status, payload = self._call(
            "GET",
            f"_apis/wit/workitems/{int(number)}",
            params={"$expand": "all", "api-version": API_VERSION},
        )
        if status == 404:
            return None
        if status >= 400:
            self._raise(status, payload, action="get")
        if not isinstance(payload, dict) or not payload.get("id"):
            return None
        return self._load(payload, with_comments=True)

    def comment(self, number: int, body: str) -> WorkItem:
        text = str(body or "")
        if not text.strip():
            raise ValueError("comment body must be non-empty")
        status, payload = self._call(
            "POST",
            f"_apis/wit/workItems/{int(number)}/comments",
            params={"api-version": COMMENTS_API_VERSION},
            payload={"text": text},
        )
        if status == 404:
            raise KeyError(f"work item not found: {number}")
        if status >= 400:
            self._raise(status, payload, action="comment")
        item = self.get(number)
        if item is None:
            raise KeyError(f"work item not found: {number}")
        return item

    def set_tags(self, number: int, tags: list[str]) -> WorkItem:
        status, payload = self._call(
            "PATCH",
            f"_apis/wit/workitems/{int(number)}",
            params={"api-version": API_VERSION},
            payload=[
                {
                    "op": "add",
                    "path": "/fields/System.Tags",
                    "value": "; ".join(tags),
                }
            ],
            content_type="application/json-patch+json",
        )
        if status == 404:
            raise KeyError(f"work item not found: {number}")
        if status >= 400:
            self._raise(status, payload, action="mark")
        if isinstance(payload, dict) and payload.get("id"):
            return self._load(payload, with_comments=True)
        item = self.get(number)
        if item is None:
            raise KeyError(f"work item not found: {number}")
        return item


def recorded_path(url: str) -> str:
    """Path + query without host. Used by recorded transports in tests."""
    parsed = urlparse(url)
    return parsed.path + (f"?{parsed.query}" if parsed.query else "")
