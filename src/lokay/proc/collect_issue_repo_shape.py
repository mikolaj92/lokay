"""Collect deterministic repository-shape evidence for issue triage."""

from __future__ import annotations
from lokay.intake import probe_repo_shape


def collect(*, clone_path) -> dict:
    shape = probe_repo_shape(clone_path)
    return {
        "ok": True,
        "collected": shape.kind != "unknown",
        "evidence_kind": "repo_shape",
        "additional_evidence": shape.to_dict(),
    }
