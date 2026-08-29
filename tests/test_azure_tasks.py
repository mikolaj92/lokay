"""Azure Boards tasks plugin: list, get, comment, mark. No network."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest

from lokay.azure_boards import AzureBoardsClient, AzureLoginError, recorded_path
from lokay.azure_tasks import AzureTasks, load_tasks
from lokay.tasks import MARKS, TaskId, sito_park


def _item(
    number: int,
    *,
    title: str = "",
    description: str = "",
    state: str = "Active",
    tags: str = "",
    assigned: str = "",
    author: str = "ada",
    comments: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": number,
        "rev": 1,
        "fields": {
            "System.Id": number,
            "System.Title": title,
            "System.Description": description,
            "System.State": state,
            "System.Tags": tags,
            "System.AssignedTo": {"uniqueName": assigned} if assigned else "",
            "System.CreatedBy": {"uniqueName": author},
        },
        "_comments": list(comments or []),
    }


class RecordedAzure:
    """Recorded Azure Boards REST. No sockets."""

    def __init__(self, items: list[dict[str, Any]]) -> None:
        self.items = {int(row["id"]): dict(row) for row in items}
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
        query = parse_qs(parsed.query)
        payload = json.loads(body.decode("utf-8")) if body else None
        self.calls.append((method, recorded_path(url), payload))
        if "Authorization" not in headers:
            return 401, {"message": "no login"}

        if method == "POST" and path.endswith("/_apis/wit/wiql"):
            open_ids = [
                {"id": item["id"]}
                for item in self.items.values()
                if str(item["fields"].get("System.State") or "")
                not in {"Closed", "Done", "Removed", "Completed"}
            ]
            return 200, {"workItems": open_ids}

        if method == "GET" and path.endswith("/_apis/wit/workitems"):
            ids = [int(x) for x in (query.get("ids") or [""])[0].split(",") if x]
            return 200, {"value": [self._public(n) for n in ids if n in self.items]}

        number = _work_item_id(path)
        if number is None:
            return 404, {"message": "not a work item"}

        if method == "GET" and path.endswith("/comments"):
            item = self.items.get(number)
            if item is None:
                return 404, {"message": "not found"}
            return 200, {
                "comments": [{"text": text} for text in item.get("_comments") or []]
            }

        if method == "POST" and path.endswith("/comments"):
            item = self.items.get(number)
            if item is None:
                return 404, {"message": "not found"}
            text = str((payload or {}).get("text") or "")
            item.setdefault("_comments", []).append(text)
            return 200, {"text": text}

        if method == "GET":
            item = self.items.get(number)
            if item is None:
                return 404, {"message": "not found"}
            return 200, self._public(number)

        if method == "PATCH":
            item = self.items.get(number)
            if item is None:
                return 404, {"message": "not found"}
            for op in payload or []:
                if op.get("path") == "/fields/System.Tags":
                    item["fields"]["System.Tags"] = op.get("value") or ""
                if op.get("path") == "/fields/System.State":
                    raise AssertionError("mark must not write System.State")
            return 200, self._public(number)

        return 404, {"message": f"unrecorded {method} {path}"}

    def _public(self, number: int) -> dict[str, Any]:
        item = self.items[number]
        return {"id": item["id"], "rev": item.get("rev", 1), "fields": dict(item["fields"])}


def _work_item_id(path: str) -> int | None:
    parts = [p for p in path.split("/") if p]
    if "workitems" not in [p.lower() for p in parts] and "workItems" not in parts:
        return None
    for index, part in enumerate(parts):
        if part.lower() == "workitems" and index + 1 < len(parts):
            token = parts[index + 1]
            if token.isdigit():
                return int(token)
    return None


def _source(transport: RecordedAzure, *, target: str = "contoso/board") -> AzureTasks:
    client = AzureBoardsClient(
        organization="contoso",
        project="board",
        token="recorded",
        transport=transport,
    )
    return AzureTasks(target=target, client=client)


def test_catalog_row_loads_azure_and_ignores_prs_repo():
    transport = RecordedAzure([_item(12, title="first")])
    row = {
        "issues": {"plugin": "azure", "target": "contoso/board"},
        "prs": {"plugin": "github", "target": "mikolaj92/lokay"},
        "repo": {"plugin": "azure", "target": "contoso/board/app"},
    }
    source = load_tasks(row, transport=transport, env={"AZURE_DEVOPS_PAT": "recorded"})
    assert isinstance(source, AzureTasks)
    assert source.plugin == "azure"
    assert source.target == "contoso/board"
    listed = source.list_open()
    assert [task.number for task in listed] == [12]
    assert all(task.plugin == "azure" and task.target == "contoso/board" for task in listed)


def test_list_get_comment_mark_from_recorded_responses():
    transport = RecordedAzure(
        [
            _item(12, title="first", description="do it", assigned="mill"),
            _item(15, title="second"),
            _item(9, title="done", state="Closed"),
        ]
    )
    source = _source(transport)
    listed = source.list_open()
    assert [task.number for task in listed] == [12, 15]
    one = source.get(listed[0].id)
    assert one is not None
    assert one.id == TaskId("azure", "contoso/board", 12)
    assert one.title == "first"
    assert one.body == "do it"
    assert one.assignees == ["mill"]
    assert one.state == "OPEN"

    source.comment(one.id, "working")
    ready = source.mark(one.id, "ready")
    assert ready.mark == "ready"
    assert ready.state == "OPEN"
    assert "ai:ready" in ready.labels
    assert source.get(one.id).comments == ["working"]
    patch_bodies = [payload for method, _, payload in transport.calls if method == "PATCH"]
    assert patch_bodies
    assert all(
        all(op.get("path") != "/fields/System.State" for op in (body or []))
        for body in patch_bodies
    )


def test_mark_park_ready_blocked_never_closes():
    transport = RecordedAzure([_item(8, title="open work", tags="ai:ready")])
    source = _source(transport)
    identity = TaskId("azure", "contoso/board", 8)
    for kind in sorted(MARKS):
        out = source.mark(identity, kind)
        assert out.mark == kind
        assert out.state == "OPEN"
        assert out.state != "CLOSED"
    assert source.get(identity).state == "OPEN"
    assert [task.number for task in source.list_open()] == [8]


def test_sito_parks_foreign_open_task_and_does_not_close():
    transport = RecordedAzure(
        [_item(42, title="someone else's work", assigned="PSyron", tags="ai:ready")]
    )
    source = _source(transport)
    identity = TaskId("azure", "contoso/board", 42)
    out = sito_park(source, identity, "foreign_assignee")
    assert out.state == "OPEN"
    assert out.mark == "park"
    assert "ai:blocked" in out.labels
    assert "ai:ready" not in out.labels
    assert any("Parked" in body for body in out.comments)
    assert source.get(identity).state != "CLOSED"
    assert [task.number for task in source.list_open()] == [42]


def test_no_login_says_so_and_does_not_fake_success():
    row = {"issues": {"plugin": "azure", "target": "contoso/board"}}
    with pytest.raises(AzureLoginError, match="no login"):
        load_tasks(row, env={})
    client = AzureBoardsClient(
        organization="contoso",
        project="board",
        token="",
        transport=RecordedAzure([_item(1, title="hidden")]),
    )
    source = AzureTasks(target="contoso/board", client=client)
    with pytest.raises(AzureLoginError, match="no login"):
        source.list_open()
    with pytest.raises(AzureLoginError, match="no login"):
        source.get(TaskId("azure", "contoso/board", 1))
    with pytest.raises(AzureLoginError, match="no login"):
        source.comment(TaskId("azure", "contoso/board", 1), "x")
    with pytest.raises(AzureLoginError, match="no login"):
        source.mark(TaskId("azure", "contoso/board", 1), "ready")


def test_source_has_no_pr_or_repo():
    source = _source(RecordedAzure([]))
    names = {name for name in dir(source) if not name.startswith("_")}
    forbidden = {
        "branch",
        "clone",
        "close",
        "git",
        "list_prs",
        "merge",
        "pr",
        "prs",
        "repo",
        "worktree",
    }
    assert names.isdisjoint(forbidden)
    assert not hasattr(source, "list_prs")
    assert not hasattr(source, "merge")
    assert not hasattr(source, "clone")
    assert not hasattr(source, "close")
    assert not hasattr(source, "repo")
    assert "repo" not in source.__dict__
    assert not hasattr(AzureTasks, "list_prs")
    assert not hasattr(AzureBoardsClient, "list_prs")
    assert not hasattr(AzureBoardsClient, "merge")


def test_get_is_identity_bound_and_unknown_plugin_does_not_load():
    source = _source(RecordedAzure([_item(1, title="open"), _item(2, title="done", state="Closed")]))
    assert source.get(TaskId("azure", "contoso/board", 2)).state == "CLOSED"
    assert source.get(TaskId("github", "contoso/board", 1)) is None
    assert source.get(TaskId("azure", "other/board", 1)) is None
    with pytest.raises(KeyError):
        source.comment(TaskId("github", "contoso/board", 1), "no")
    with pytest.raises(ValueError):
        source.mark(TaskId("azure", "contoso/board", 1), "close")
    with pytest.raises(ValueError, match="not azure"):
        load_tasks(
            {"issues": {"plugin": "github", "target": "mikolaj92/lokay"}},
            env={"AZURE_DEVOPS_PAT": "x"},
        )
