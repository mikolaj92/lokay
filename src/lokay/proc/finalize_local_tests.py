"""Choose publication or repair terminal after one bounded repair pass."""

from __future__ import annotations
from lokay.coding_boundary import finalize_tests


def finalize(first: dict, repaired: dict, *, applicable: bool = True) -> dict:
    return finalize_tests(first, repaired, applicable)
