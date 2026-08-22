"""Hermetic scope tests for the resolve-conflicts pass atom."""

from __future__ import annotations

from pathlib import Path


from lokay.passkit import io as pass_io


def _conflicting_pr(number: int) -> dict[str, object]:
    return {
        "number": number,
        "head_ref": f"ai/fix/{number}-conflict",
        "mergeable": "CONFLICTING",
        "title": f"issue {number}",
    }


def _write_pass(tmp_path: Path, repos: list[str]) -> Path:
    pass_dir = tmp_path / "pass"
    pass_dir.mkdir()
    pass_io.write_json(
        pass_io.begin_path(pass_dir),
        {
            "repos": repos,
            "branch_prefix": "ai/fix/",
            "stuck_path": str(tmp_path / "stuck.json"),
        },
    )
    pass_io.write_json(
        pass_io.working_path(pass_dir),
        {
            "actions": [],
            "progress": 0,
            "stuck": {"issues": {}},
            "prs_by_repo": {
                repo: [_conflicting_pr(index + 20)]
                for index, repo in enumerate(repos)
            },
            "ready_by_repo": {},
            "remaining_prs": len(repos),
            "remaining_ready": 0,
            "merge_conflicts": 0,
        },
    )
    return pass_dir




