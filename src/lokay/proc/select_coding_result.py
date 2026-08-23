"""Select the initial coding result after one bounded invalid-JSON retry."""

from __future__ import annotations
from lokay.coding_boundary import select_initial


def select(first: dict, retry: dict) -> dict:
    return select_initial(first, retry)
