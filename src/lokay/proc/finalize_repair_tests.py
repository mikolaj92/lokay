"""Choose PR-repair publication or terminal after bounded tests."""

from lokay.repair_boundary import finalize_tests


def finalize(first: dict, second: dict, *, applicable: bool = True) -> dict:
    return finalize_tests(first, second, applicable=applicable)
