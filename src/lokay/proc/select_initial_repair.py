"""Select initial repair result after one invalid-JSON retry."""

from lokay.repair_boundary import select_initial


def select(first: dict, retry: dict) -> dict:
    return select_initial(first, retry)
