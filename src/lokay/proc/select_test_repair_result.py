"""Select the single test-repair agent result."""

from lokay.repair_boundary import select_test_repair


def select(initial_test: dict, validation: dict, *, applicable: bool = True) -> dict:
    return select_test_repair(initial_test, validation, applicable=applicable)
