"""Select the single evidence-round coding result."""

from __future__ import annotations
from lokay.coding_boundary import select_evidence


def select(initial: dict, validation: dict) -> dict:
    return select_evidence(initial, validation)
