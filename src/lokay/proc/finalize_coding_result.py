"""Choose the authoritative coding result after the bounded evidence round."""

from __future__ import annotations
from lokay.coding_boundary import finalize


def finalize_result(initial: dict, evidence: dict) -> dict:
    return finalize(initial, evidence)
