"""Select the bounded repair-agent result."""

from __future__ import annotations
from lokay.coding_boundary import select_repair


def select(validation: dict, *, applicable: bool = True) -> dict:
    return select_repair(validation, applicable)
