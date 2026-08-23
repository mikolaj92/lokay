"""Select the single evidence-round PR repair result."""

from lokay.repair_boundary import select_evidence


def select(initial: dict, validation: dict) -> dict:
    return select_evidence(initial, validation)
