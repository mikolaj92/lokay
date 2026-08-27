"""Pick one isolated Fala journal directory for one child process."""

from __future__ import annotations

import argparse
from pathlib import Path

from lokay.envelope import emit_exit, ok

_ISOLATED = {
    "issue_to_pr": "i2pr",
    "issue_to_pr_delivery": "i2pr-delivery",
    "issue_split": "issue-split",
    "coding_execution": "coding",
}


def _ticket_slug(repo: str, issue: int | None) -> str | None:
    if issue is None or "/" not in str(repo):
        return None
    owner, name = str(repo).split("/", 1)
    if not owner or not name:
        return None
    return f"{owner}__{name}__{int(issue)}"


def journal_dir(
    *,
    path_id: str,
    repo: str,
    issue: int | None,
    home: Path | None = None,
) -> Path:
    """Return the journal directory for one Fala host.

    Isolated children never share ``~/.lokay/fala/state.sqlite``. One Fala,
    one journal. A child is its own process with its own journal.
    """
    root = (home or Path.home()) / ".lokay" / "fala"
    family = _ISOLATED.get(str(path_id) or "")
    if not family:
        return root
    slug = _ticket_slug(repo, issue)
    if slug is None:
        return root
    return root / family / slug


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lokay-child-fala-journal")
    parser.add_argument("--path-id", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--issue", type=int)
    parser.add_argument("--lokay-home")
    args = parser.parse_args(argv)
    work = journal_dir(
        path_id=args.path_id,
        repo=args.repo,
        issue=args.issue,
        home=Path(args.lokay_home) if args.lokay_home else None,
    )
    return emit_exit(ok(dir=str(work), db=str(work / "state.sqlite"), path_id=args.path_id))


if __name__ == "__main__":
    raise SystemExit(main())
