"""Resolve the issue number encoded by one closed conflict branch."""

from lokay.passkit.io import begin_path, read_json
from lokay.stuck import issue_number_from_branch


def resolve(*, pass_dir: str, closed: dict) -> dict:
    begin = read_json(begin_path(pass_dir))
    number = issue_number_from_branch(
        str(closed.get("head_ref") or ""),
        branch_prefix=str(begin.get("branch_prefix") or "ai/fix/"),
    )
    return {
        "ok": True,
        "route": "issue" if number is not None else "no_issue",
        "issue": number,
        **closed,
    }
