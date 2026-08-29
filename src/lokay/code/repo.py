"""Repo block: path, clone, branch, worktree. No tasks. No PR sieve."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from lokay.code.contract import CodeTarget


class RepoBlock(Protocol):
    """Local tree for one code target."""

    @property
    def target(self) -> CodeTarget: ...

    def path(self) -> Path:
        """Give the local path."""
        ...

    def clone(self) -> Path:
        """Make or refresh the local copy. Return its path."""
        ...

    def branch(self, name: str) -> str:
        """Make or return a branch on this target."""
        ...

    def worktree(self, name: str) -> Path:
        """Give a working copy for a branch name."""
        ...
