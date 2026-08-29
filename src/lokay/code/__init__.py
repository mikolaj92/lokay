"""Code place: repo and PR are two blocks on one target.

Tasks may live elsewhere. A PR cannot be bound to a different clone.
"""

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
    "CodeTarget",
    "MemoryCode",
    "PrBlock",
    "RepoBlock",
    "bind_code",
)
