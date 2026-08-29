"""Code place: repo and PR are two blocks on one target.

Tasks may live elsewhere. A PR cannot be bound to a different clone.
"""

from lokay.code.catalog import CodeSlot, load_code, parse_code_slot, slot_from_repo
from lokay.code.contract import (
    CODE_BLOCKS,
    CodeContract,
    CodeContractError,
    CodeError,
    CodeTarget,
    bind_code,
)
from lokay.code.memory import MemoryCode
from lokay.code.pr import Change, ChangeChecks, PrBlock
from lokay.code.repo import RepoBlock

__all__ = (
    "CODE_BLOCKS",
    "Change",
    "ChangeChecks",
    "CodeContract",
    "CodeContractError",
    "CodeError",
    "CodeSlot",
    "CodeTarget",
    "AzureCode",
    "GithubCode",
    "MemoryCode",
    "PrBlock",
    "RepoBlock",
    "bind_code",
    "load_code",
    "parse_code_slot",
    "slot_from_repo",
)


def __getattr__(name: str):
    if name == "GithubCode":
        from lokay.code.github import GithubCode

        return GithubCode
    if name == "AzureCode":
        from lokay.code.azure import AzureCode

        return AzureCode
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
