"""Validate one coding-agent response against the closed schema."""

from __future__ import annotations
from lokay.coding_boundary import validate_output


def validate(stdout: str) -> dict:
    return validate_output(stdout)
