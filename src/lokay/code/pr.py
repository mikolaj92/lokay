"""PR block: list, get, checks, comment, merge-commit, close.

No tasks. No clone. Merge is merge-commit, not squash.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from lokay.code.contract import CodeError, CodeTarget


@dataclass(frozen=True)
class Change:
    """One change on a code target. Identity is plugin + target + number."""

    target: CodeTarget
    number: int
    title: str
    body: str
    head: str
    state: str
    comments: tuple[str, ...] = ()
    checks_status: str = "none"
    merge_method: str | None = None


@dataclass(frozen=True)
class ChangeChecks:
    """Checks row for one change. No gh."""

    status: str
    green: bool


class PrBlock(Protocol):
    """Sieve for changes that live on the same target as the repo."""

    @property
    def target(self) -> CodeTarget: ...

    def list_open(self) -> list[Change]:
        """List open changes."""
        ...

    def get(self, number: int) -> Change:
        """Get one change."""
        ...

    def checks(self, number: int) -> ChangeChecks:
        """Read checks for one change."""
        ...

    def comment(self, number: int, body: str) -> Change:
        """Add a review comment."""
        ...

    def merge_commit(self, number: int) -> Change:
        """Merge with a merge commit. Not squash."""
        ...

    def close(self, number: int) -> Change:
        """Close without merging."""
        ...
