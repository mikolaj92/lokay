"""Reduce one physical local-test result to a direct Fala route."""

from __future__ import annotations
from lokay.coding_boundary import select_test


def select(result: dict, *, applicable: bool = True) -> dict:
    return select_test(result, applicable)
