"""In-memory code plugin. One target owns repo and PR. No tasks. No gh."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

from lokay.code.contract import CodeError, CodeTarget
from lokay.code.pr import Change, ChangeChecks


def _need_name(name: str, *, what: str) -> str:
    text = str(name or "").strip()
    if not text:
        raise CodeError(f"{what} name must be non-empty")
    return text


@dataclass
class _Store:
    root: Path
    branches: dict[str, str] = field(default_factory=dict)
    changes: dict[int, Change] = field(default_factory=dict)


class MemoryRepo:
    """Repo block for the in-memory plugin."""

    def __init__(self, target: CodeTarget, store: _Store) -> None:
        self.target = target
        self._store = store

    def path(self) -> Path:
        return self._store.root

    def clone(self) -> Path:
        self._store.root.mkdir(parents=True, exist_ok=True)
        return self._store.root

    def branch(self, name: str) -> str:
        head = _need_name(name, what="branch")
        self.clone()
        self._store.branches[head] = head
        return head

    def worktree(self, name: str) -> Path:
        head = _need_name(name, what="worktree")
        self.clone()
        path = self._store.root / "worktrees" / head.replace("/", "-")
        path.mkdir(parents=True, exist_ok=True)
        return path


class MemoryPr:
    """PR block for the in-memory plugin."""

    def __init__(self, target: CodeTarget, store: _Store) -> None:
        self.target = target
        self._store = store

    def _get(self, number: int) -> Change:
        try:
            return self._store.changes[int(number)]
        except KeyError as exc:
            raise CodeError(f"change {number} not on {self.target}") from exc

    def _put(self, change: Change) -> Change:
        self._store.changes[change.number] = change
        return change

    def list_open(self) -> list[Change]:
        return [row for row in self._store.changes.values() if row.state == "open"]

    def get(self, number: int) -> Change:
        return self._get(number)

    def checks(self, number: int) -> ChangeChecks:
        row = self._get(number)
        return ChangeChecks(status=row.checks_status, green=row.checks_status == "passed")

    def comment(self, number: int, body: str) -> Change:
        text = str(body or "").strip()
        if not text:
            raise CodeError("comment body must be non-empty")
        row = self._get(number)
        return self._put(replace(row, comments=row.comments + (text,)))

    def merge_commit(self, number: int) -> Change:
        row = self._get(number)
        if row.state != "open":
            raise CodeError(f"change {number} is {row.state}, cannot merge-commit")
        return self._put(replace(row, state="merged", merge_method="merge"))

    def close(self, number: int) -> Change:
        row = self._get(number)
        if row.state != "open":
            raise CodeError(f"change {number} is {row.state}, cannot close")
        return self._put(replace(row, state="closed"))


class MemoryCode:
    """One in-memory host. Repo and PR share this target. No task list."""

    def __init__(self, target: CodeTarget, root: Path) -> None:
        self.target = target
        self._store = _Store(root=Path(root))
        self.repo = MemoryRepo(target, self._store)
        self.pr = MemoryPr(target, self._store)

    def put_change(
        self,
        number: int,
        *,
        title: str,
        head: str,
        body: str = "",
        checks_status: str = "none",
    ) -> Change:
        """Place an open change on this target. Not a task."""
        change = Change(
            target=self.target,
            number=int(number),
            title=str(title),
            body=str(body),
            head=_need_name(head, what="head"),
            state="open",
            checks_status=str(checks_status or "none"),
        )
        self._store.changes[change.number] = change
        return change
