"""Azure Boards tasks plugin. Work item = task. Parent calls the contract."""

from __future__ import annotations

from typing import Any, Mapping

from lokay.azure_boards import AzureBoardsClient, AzureLoginError, WorkItem
from lokay.tasks import Task, TaskId, _require_mark

PLUGIN = "azure"


def issues_slot(row: dict[str, Any]) -> tuple[str, str]:
    """Read issues.plugin / issues.target. Ignore prs and repo."""
    issues = row.get("issues")
    if not isinstance(issues, dict):
        raise ValueError("catalog row needs issues.plugin and issues.target")
    plugin = str(issues.get("plugin") or "").strip()
    target = str(issues.get("target") or "").strip()
    if not plugin or not target:
        raise ValueError("catalog row needs issues.plugin and issues.target")
    return plugin, target


def load_tasks(
    row: dict[str, Any],
    *,
    env: Mapping[str, str] | None = None,
    client: AzureBoardsClient | None = None,
    transport: Any = None,
) -> AzureTasks:
    """Catalog `issues.plugin: azure` loads this plugin. Does not read prs/repo."""
    plugin, target = issues_slot(row)
    if plugin != PLUGIN:
        raise ValueError(f"issues.plugin {plugin!r} is not azure")
    if client is None:
        client = AzureBoardsClient.from_env(target=target, env=env, transport=transport)
    return AzureTasks(target=target, client=client)


class AzureTasks:
    """Tasks executor for Azure Boards work items. Zero PR, clone, git, merge."""

    def __init__(self, *, target: str, client: AzureBoardsClient) -> None:
        identity = TaskId(PLUGIN, target, 1)
        self.plugin = identity.plugin
        self.target = identity.target
        self._client = client

    def _same(self, identity: TaskId) -> bool:
        return identity.plugin == self.plugin and identity.target == self.target

    def _owned(self, identity: TaskId) -> Task | None:
        if not self._same(identity):
            return None
        item = self._client.get(identity.number)
        if item is None:
            return None
        return self._to_task(item)

    def _to_task(self, item: WorkItem) -> Task:
        labels = list(item.tags)
        mark = None
        if "ai:ready" in labels:
            mark = "ready"
        elif "ai:park" in labels:
            mark = "park"
        elif "ai:blocked" in labels:
            mark = "blocked"
        return Task(
            plugin=self.plugin,
            target=self.target,
            number=item.id,
            title=item.title,
            body=item.description,
            labels=labels,
            assignees=list(item.assignees),
            state="CLOSED" if item.closed else "OPEN",
            author=item.author,
            mark=mark,
            comments=list(item.comments),
        )

    def list_open(self) -> list[Task]:
        return [self._to_task(item) for item in self._client.list_open()]

    def get(self, identity: TaskId) -> Task | None:
        return self._owned(identity)

    def comment(self, identity: TaskId, body: str) -> Task:
        if not self._same(identity):
            raise KeyError(
                f"task not found: {identity.plugin}+{identity.target}+{identity.number}"
            )
        try:
            item = self._client.comment(identity.number, body)
        except KeyError as exc:
            raise KeyError(
                f"task not found: {identity.plugin}+{identity.target}+{identity.number}"
            ) from exc
        return self._to_task(item)

    def mark(self, identity: TaskId, kind: str) -> Task:
        if not self._same(identity):
            raise KeyError(
                f"task not found: {identity.plugin}+{identity.target}+{identity.number}"
            )
        token = _require_mark(kind)
        current = self._client.get(identity.number)
        if current is None:
            raise KeyError(
                f"task not found: {identity.plugin}+{identity.target}+{identity.number}"
            )
        drop = {"ai:ready", "work:ready", "ai:blocked", "ai:park"}
        labels = [tag for tag in current.tags if tag not in drop]
        if token == "ready":
            labels.append("ai:ready")
        elif token == "park":
            labels.extend(["ai:blocked", "ai:park"])
        else:
            labels.append("ai:blocked")
        try:
            item = self._client.set_tags(identity.number, labels)
        except KeyError as exc:
            raise KeyError(
                f"task not found: {identity.plugin}+{identity.target}+{identity.number}"
            ) from exc
        task = self._to_task(item)
        # Park / ready / blocked stay open. This plugin has no close.
        task.mark = token
        task.state = "OPEN"
        return task


# Re-export so callers can catch the explicit no-login failure.
LoginError = AzureLoginError
