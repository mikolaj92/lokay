"""Purely classify one changed-path set as real, plan-only, or empty."""

from lokay.git_real_diff import classify_changed_paths


def classify(changed: dict) -> dict:
    return {
        "ok": True,
        "kind": classify_changed_paths(list(changed.get("paths") or [])),
    }
