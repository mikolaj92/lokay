"""Select the single test-repair agent result."""

from lokay.repair_boundary import select_test_repair


def select(validation: dict, *, applicable: bool = True) -> dict:
    return select_test_repair(validation, applicable=applicable)
