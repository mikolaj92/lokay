"""Choose the authoritative bounded PR repair result."""

from lokay.repair_boundary import finalize


def finalize_result(initial: dict, evidence: dict) -> dict:
    return finalize(initial, evidence)
