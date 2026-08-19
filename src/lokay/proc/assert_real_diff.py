"""Refuse plan-only diffs and source changes outside localized scope.

A commit/PR that only ships ``.lokay/approach.md`` / ``.lokay/localize.json``
is not progress. When localize has paths, changes below ``src/``, ``tests/``, or
``fala/`` must fall within them. Callers must not ``pr_create`` on refusal.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from lokay.envelope import emit_exit, err, ok
from lokay.git_real_diff import classify_changed_paths, list_changed_paths
from lokay.localize import extract_issue_file_paths
from lokay.proc._common import runner


_SCOPED_ROOTS = {"fala", "src", "tests"}
_TICKET_FILES_HEADING_RE = re.compile(
    r"(?im)^\s*#{1,6}\s+(?:zmiana|files?)\s*:?[ \t]*$"
)


def _localize_paths(worktree: Path) -> list[str]:
    localize = worktree / ".lokay" / "localize.json"
    if not localize.is_file():
        return []
    payload = json.loads(localize.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(".lokay/localize.json must contain an object")
    paths = payload.get("paths", [])
    if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
        raise ValueError(".lokay/localize.json paths must be a list of strings")
    return [path.removeprefix("./").rstrip("/") for path in paths if path.rstrip("/")]


def _off_goal_paths(changed: list[str], localized: list[str]) -> list[str]:
    def allowed(path: str) -> bool:
        return any(path == scope or path.startswith(f"{scope}/") for scope in localized)

    normalized = [path.removeprefix("./") for path in changed]
    return [
        path
        for path in normalized
        if path.split("/", 1)[0] in _SCOPED_ROOTS and not allowed(path)
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-assert-real-diff")
    parser.add_argument("--worktree", required=True)
    parser.add_argument("--base", default="origin/main")
    parser.add_argument(
        "--issue-body",
        help="issue body used to require a diff in an explicit Zmiana/Files scope",
    )
    args = parser.parse_args(argv)
    worktree = Path(args.worktree).resolve()
    if not worktree.is_dir():
        return emit_exit(err("worktree is not a directory", worktree=str(worktree)))
    try:
        paths = list_changed_paths(runner(), worktree, base=str(args.base))
    except Exception as exc:  # noqa: BLE001
        return emit_exit(err(str(exc), worktree=str(worktree)))
    kind = classify_changed_paths(paths)
    try:
        localized = _localize_paths(worktree)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return emit_exit(
            err(
                f"refusing: invalid localize evidence: {exc}",
                reason="invalid_localize",
                kind=kind,
                real=False,
                paths=paths,
                worktree=str(worktree),
                base=str(args.base),
            )
        )
    off_goal = _off_goal_paths(paths, localized) if localized else []
    if off_goal:
        return emit_exit(
            err(
                "refusing: changed source paths fall outside localize scope",
                reason="off_goal",
                kind="off_goal",
                real=False,
                paths=paths,
                off_goal_paths=off_goal,
                localized_paths=localized,
                worktree=str(worktree),
                base=str(args.base),
            )
        )
    issue_body = args.issue_body or ""
    if _TICKET_FILES_HEADING_RE.search(issue_body):
        required = list(extract_issue_file_paths(issue_body))
        normalized_changed = {path.removeprefix("./") for path in paths}
        if not required or normalized_changed.isdisjoint(required):
            return emit_exit(
                err(
                    "refusing: diff does not contain a file declared by the issue",
                    reason="ticket_scope_miss",
                    kind="off_goal",
                    real=False,
                    paths=paths,
                    required_paths=required,
                    worktree=str(worktree),
                    base=str(args.base),
                )
            )
    if kind == "real":
        return emit_exit(
            ok(
                real=True,
                kind=kind,
                paths=paths,
                worktree=str(worktree),
                base=str(args.base),
            )
        )
    reason = "plan_only" if kind == "plan_only" else "zero_diff"
    message = (
        "refusing: diff is only plan/localize evidence "
        "(.lokay/approach.md / .lokay/localize.json); not progress"
        if kind == "plan_only"
        else "refusing: empty diff vs base; not progress"
    )
    return emit_exit(
        err(
            message,
            reason=reason,
            kind=kind,
            real=False,
            paths=paths,
            worktree=str(worktree),
            base=str(args.base),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
