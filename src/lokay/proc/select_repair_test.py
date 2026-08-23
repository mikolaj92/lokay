"""Reduce a physical PR-repair test result to a Fala route."""

from lokay.repair_boundary import select_test


def select(test: dict, *, applicable: bool = True) -> dict:
    return select_test(test, applicable=applicable)
