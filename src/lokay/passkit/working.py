"""Load/save mutable factory-pass working state (shared by closeout atoms)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lokay.passkit import io as pass_io
from lokay.passkit.support import is_manual_pr


def load_begin_working(pass_dir: str) -> tuple[dict[str, Any], dict[str, Any]]:
    begin = pass_io.read_json(pass_io.begin_path(pass_dir))
    working = pass_io.read_json(pass_io.working_path(pass_dir))
    return begin, working


def stuck_path_of(begin: dict[str, Any]) -> Path:
    return Path(str(begin.get("stuck_path") or ""))


def recount_prs(working: dict[str, Any]) -> None:
    prs_by_repo = dict(working.get("prs_by_repo") or {})
    working["remaining_prs"] = sum(len(prs) for prs in prs_by_repo.values())
    working["actionable_prs"] = sum(
        not is_manual_pr(pr) for prs in prs_by_repo.values() for pr in prs
    )
    working["manual_prs"] = sum(
        is_manual_pr(pr) for prs in prs_by_repo.values() for pr in prs
    )


def save_begin_working(
    pass_dir: str, begin: dict[str, Any], working: dict[str, Any]
) -> None:
    pass_io.write_json(pass_io.begin_path(pass_dir), begin)
    pass_io.write_json(pass_io.working_path(pass_dir), working)
