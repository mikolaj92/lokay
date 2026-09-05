"""Task consumption contract. One plugin: list, get, comment, mark.

Identity is plugin + target + number. Zero PR, clone, git, merge.
Sito parks a foreign open task; it does not close it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

MARKS = frozenset({"park", "ready", "blocked"})


@dataclass(frozen=True)
class TaskId:
    """Stable identity of one task. Not a repo and not a PR."""

    plugin: str
    target: str
    number: int

    def __post_init__(self) -> None:
        plugin = str(self.plugin or "").strip()
        target = str(self.target or "").strip()
        number = int(self.number)
        if not plugin:
            raise ValueError("plugin must be non-empty")
        if not target:
            raise ValueError("target must be non-empty")
        if number < 1:
            raise ValueError("number must be >= 1")
        object.__setattr__(self, "plugin", plugin)
        object.__setattr__(self, "target", target)
        object.__setattr__(self, "number", number)


@dataclass
class Task:
    plugin: str
    target: str
    number: int
    title: str = ""
    body: str = ""
    labels: list[str] = field(default_factory=list)
    assignees: list[str] = field(default_factory=list)
    state: str = "OPEN"
    author: str = ""
    mark: str | None = None
    comments: list[str] = field(default_factory=list)

    @property
    def id(self) -> TaskId:
        return TaskId(self.plugin, self.target, self.number)


class Tasks(Protocol):
    """Parent calls this. It does not know who is on the other side."""

    plugin: str
    target: str

    def list_open(self) -> list[Task]: ...

    def list_labeled(self, label: str) -> list[Task]: ...

    def get(self, identity: TaskId) -> Task | None: ...

    def comment(self, identity: TaskId, body: str) -> Task: ...

    def mark(self, identity: TaskId, kind: str) -> Task: ...


def _require_mark(kind: str) -> str:
    token = str(kind or "").strip().lower()
    if token not in MARKS:
        raise ValueError(f"mark must be one of {sorted(MARKS)}")
    return token


def sito_park(source: Tasks, identity: TaskId, reason: str) -> Task:
    """Park a sito close verdict. Comment and mark; never close."""
    source.comment(identity, f"Parked: {reason}")
    task = source.mark(identity, "park")
    if str(task.state or "").upper() == "CLOSED":
        raise RuntimeError("sito must not close an open task")
    return task


class MemoryTasks:
    """In-memory source. Four operations. No PR, no repo, no close."""

    def __init__(self, *, plugin: str = "memory", target: str) -> None:
        identity = TaskId(plugin, target, 1)
        self.plugin = identity.plugin
        self.target = identity.target
        self._tasks: dict[int, Task] = {}

    def seed(
        self,
        number: int,
        *,
        title: str = "",
        body: str = "",
        labels: list[str] | None = None,
        assignees: list[str] | None = None,
        state: str = "OPEN",
        author: str = "",
        mark: str | None = None,
    ) -> Task:
        task = Task(
            plugin=self.plugin,
            target=self.target,
            number=int(number),
            title=str(title or ""),
            body=str(body or ""),
            labels=list(labels or []),
            assignees=list(assignees or []),
            state=str(state or "OPEN").upper(),
            author=str(author or ""),
            mark=str(mark).strip().lower() if mark else None,
        )
        if task.number < 1:
            raise ValueError("number must be >= 1")
        if task.mark is not None and task.mark not in MARKS:
            raise ValueError(f"mark must be one of {sorted(MARKS)}")
        self._tasks[task.number] = task
        return task

    def _same_source(self, identity: TaskId) -> bool:
        return identity.plugin == self.plugin and identity.target == self.target

    def _owned(self, identity: TaskId) -> Task | None:
        if not self._same_source(identity):
            return None
        return self._tasks.get(identity.number)

    def list_open(self) -> list[Task]:
        return [
            task
            for task in self._tasks.values()
            if str(task.state or "").upper() != "CLOSED"
        ]

    def list_labeled(self, label: str) -> list[Task]:
        token = str(label or "").strip()
        return [task for task in self.list_open() if token in task.labels]

    def get(self, identity: TaskId) -> Task | None:
        return self._owned(identity)

    def comment(self, identity: TaskId, body: str) -> Task:
        task = self._owned(identity)
        if task is None:
            raise KeyError(
                f"task not found: {identity.plugin}+{identity.target}+{identity.number}"
            )
        text = str(body or "")
        if not text.strip():
            raise ValueError("comment body must be non-empty")
        task.comments.append(text)
        return task

    def mark(self, identity: TaskId, kind: str) -> Task:
        task = self._owned(identity)
        if task is None:
            raise KeyError(
                f"task not found: {identity.plugin}+{identity.target}+{identity.number}"
            )
        token = _require_mark(kind)
        # Park / ready / blocked stay open. This source has no close.
        task.mark = token
        task.state = "OPEN"
        labels = [label for label in task.labels if label not in {"ai:ready", "work:ready"}]
        if token == "ready":
            if "ai:ready" not in labels:
                labels.append("ai:ready")
        else:
            if "ai:blocked" not in labels:
                labels.append("ai:blocked")
        task.labels = labels
        return task
