"""Atomic: run one deterministic intake check (JSON envelope).

Does not mutate GitHub. Evidence for superseded PRs is optional via flags.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from lokay.envelope import emit_exit, err, ok
from lokay.gh_issues import get_issue
from lokay.intake import (
    check_ambiguity,
    check_duplicate_ai_pr,
    check_open,
    check_satisfied,
    check_shape,
    check_superseded,
    probe_repo_shape,
    referenced_pr_numbers,
)
from lokay.proc._common import add_config_read, load_cfg, read_live, resolve_repo_clone, runner


_CHECKS = ("open", "superseded", "shape", "satisfied", "ambiguity", "duplicate_ai_pr")
_INTAKE_REPO = "mikolaj92/lokay"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="lokay-intake-check")
    add_config_read(p)
    p.add_argument("--repo", required=True)
    p.add_argument("--issue", required=True, type=int)
    p.add_argument("--check", required=True, choices=_CHECKS)
    p.add_argument(
        "--merged-pr",
        action="append",
        type=int,
        default=[],
        help="merged PR number evidence (repeatable); used by superseded",
    )
    p.add_argument(
        "--tracker-done",
        action="store_true",
        help="linked epic/tracker is closed/done (superseded evidence)",
    )
    p.add_argument(
        "--covering-pr",
        action="append",
        default=[],
        help="covering AI PR evidence as N[:merged|open] (repeatable)",
    )
    args = p.parse_args(argv)
    if args.repo != _INTAKE_REPO:
        return emit_exit(
            ok(
                skipped=True,
                reason="repo_not_intake_target",
                repo=args.repo,
                issue=args.issue,
                check=args.check,
            )
        )

    cfg = load_cfg(args)
    live = read_live(args)
    try:
        issue = get_issue(runner(), cfg, args.repo, args.issue, live=live)
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc)))
    if issue is None:
        return emit_exit(err(f"issue not found: {args.repo}#{args.issue}"))

    clone: Path | None
    try:
        clone = resolve_repo_clone(cfg, args.repo)
    except KeyError:
        clone = None

    name = str(args.check)
    if name == "open":
        result = check_open(state=issue.state)
    elif name == "superseded":
        result = check_superseded(
            issue,
            merged_prs=list(args.merged_pr or []),
            closed_tracker_done=bool(args.tracker_done),
        )
    elif name == "shape":
        result = check_shape(issue, probe_repo_shape(clone))
    elif name == "satisfied":
        result = check_satisfied(issue, clone_path=clone)
    elif name == "duplicate_ai_pr":
        covering = []
        for raw in args.covering_pr or []:
            text = str(raw)
            if ":" in text:
                num_s, state_s = text.split(":", 1)
                covering.append(
                    {
                        "number": int(num_s),
                        "state": state_s.upper(),
                        "merged": state_s.lower() == "merged",
                    }
                )
            else:
                covering.append({"number": int(text), "state": "OPEN", "merged": False})
        result = check_duplicate_ai_pr(issue, covering_prs=covering)
    else:
        result = check_ambiguity(issue)

    return emit_exit(
        ok(
            offline=not live,
            repo=args.repo,
            issue=issue.to_dict(),
            check=result.to_dict(),
            referenced_prs=referenced_pr_numbers(issue),
            clone_path=str(clone) if clone else None,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
