"""Collect named-path presence facts for one issue without semantic judgment."""

from __future__ import annotations
from pathlib import Path
from lokay.intake import named_add_paths, named_removal_paths
from lokay.models import Issue


def collect(*, issue_data: dict, clone_path) -> dict:
    issue = Issue.from_dict(issue_data)
    root = Path(clone_path) if clone_path else None
    names = list(dict.fromkeys([*named_add_paths(issue), *named_removal_paths(issue)]))
    rows = [
        {"path": name, "exists": bool(root and (root / name).exists())}
        for name in names
    ]
    return {
        "ok": True,
        "collected": root is not None and root.is_dir(),
        "evidence_kind": "named_paths",
        "additional_evidence": {"paths": rows},
    }
