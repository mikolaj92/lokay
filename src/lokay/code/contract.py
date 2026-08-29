"""One code contract: one target, two blocks (repo + PR).

Product law: two small blocks + a graph. This module binds the blocks.
Order stays in Fala. No gh. No task consumption.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lokay.code.pr import PrBlock
    from lokay.code.repo import RepoBlock

CODE_BLOCKS = ("repo", "pr")


class CodeContractError(ValueError):
    """Repo and PR are not the same code target."""


class CodeError(LookupError):
    """Missing change or illegal repo/PR transition."""


@dataclass(frozen=True)
class CodeTarget:
    """Plugin + target. Not owner/name. Not a task id."""

    plugin: str
    id: str

    def __post_init__(self) -> None:
        plugin = self.plugin.strip()
        ident = self.id.strip()
        if not plugin:
            raise CodeContractError("code target plugin must be non-empty")
        if not ident:
            raise CodeContractError("code target id must be non-empty")
        object.__setattr__(self, "plugin", plugin)
        object.__setattr__(self, "id", ident)

    def __str__(self) -> str:
        return f"{self.plugin}:{self.id}"


@dataclass(frozen=True)
class CodeContract:
    """One place. One target. Repo and PR blocks only."""

    target: CodeTarget
    repo: RepoBlock
    pr: PrBlock


def bind_code(
    target: CodeTarget,
    *,
    repo: RepoBlock,
    pr: PrBlock,
) -> CodeContract:
    """Bind repo and PR to one target. Two targets fail closed."""
    if repo.target != pr.target:
        raise CodeContractError(
            f"cannot split PR and repo onto two targets: "
            f"repo={repo.target} pr={pr.target}"
        )
    if repo.target != target:
        raise CodeContractError(
            f"repo target {repo.target} is not contract target {target}"
        )
    if pr.target != target:
        raise CodeContractError(
            f"PR target {pr.target} is not contract target {target}"
        )
    return CodeContract(target=target, repo=repo, pr=pr)
