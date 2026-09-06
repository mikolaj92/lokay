"""Select the bounded repair-agent result after one invalid-JSON retry."""

from __future__ import annotations
from lokay.coding_boundary import select_repair


def select(first: dict, retry: dict | None = None, *, applicable: bool = True) -> dict:
    return select_repair(first, applicable, retry)
