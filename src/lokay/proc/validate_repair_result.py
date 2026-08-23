"""Validate one PR-repair agent response against the closed schema."""

from lokay.repair_boundary import validate_output


def validate(stdout: str) -> dict:
    return validate_output(stdout)
