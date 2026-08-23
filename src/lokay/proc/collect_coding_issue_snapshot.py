"""Collect the current issue snapshot requested by the coding agent."""

from __future__ import annotations


def collect(issue: dict) -> dict:
    return {"ok": True, "evidence_kind": "issue_snapshot", "evidence": {"issue": issue}}
