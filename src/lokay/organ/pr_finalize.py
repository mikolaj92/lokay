"""Fala routing for issue-to-PR finalization."""

from __future__ import annotations

from typing import Any

from lokay.organ.common import _run_atom_main


def handle_pr_finalize(
    atom: str,
    inputs: dict[str, Any],
    up: dict[str, dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any] | None:
    from lokay.proc import list_prs, pr_label

    cfg = ctx["cfg"]
    live = ctx["live"]
    repo = ctx["repo"]

    if atom == "list_prs":
        assert repo
        return _run_atom_main(list_prs.main, [*cfg, "--repo", repo])

    if atom == "pr_label":
        branch = str(up.get("make_branch", {}).get("branch") or "")
        prs = up.get("list_prs", {}).get("prs") or []
        pr_number = next(
            (pr.get("number") for pr in prs if pr.get("head_ref") == branch),
            None,
        )
        if pr_number is None:
            created = up.get("pr_create") or {}
            candidate = created.get("pr_number") or created.get("pr")
            if isinstance(candidate, dict):
                candidate = candidate.get("number")
            if isinstance(candidate, int):
                pr_number = candidate
        if pr_number is None:
            return {
                "ok": True,
                "skipped": True,
                "reason": "pr_number_not_found",
                "branch": branch,
            }
        return _run_atom_main(
            pr_label.main,
            [*cfg, *live, "--repo", repo, "--pr", str(pr_number)],
        )

    return None
