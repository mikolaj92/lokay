"""Collect one bounded deterministic repository-shape fact."""

from pathlib import Path

from lokay.intake import probe_repo_shape


def probe(clone: dict) -> dict:
    return {
        "ok": True,
        "shape": probe_repo_shape(
            Path(clone["clone_path"]) if clone.get("clone_path") else None
        ).to_dict(),
    }
