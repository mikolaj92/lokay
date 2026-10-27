from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

from lokay.effects.git import git, git_try, samefile


def worktree(repo: Path, target: Path, branch: str, action: str, merge_commit: str | None = None) -> None:
    repo = repo.resolve()
    target = target.parent.resolve() / target.name
    if target.is_symlink() or target == repo or target.is_relative_to(repo) or repo.is_relative_to(target):
        raise ValueError("expected a separate non-symlink worktree location")
    if not samefile(git(repo, "rev-parse", "--show-toplevel"), repo):
        raise ValueError("repository top-level mismatch")
    git(repo, "check-ref-format", "--branch", branch)
    ref = f"refs/heads/{branch}"
    records = []
    for entry in git(repo, "worktree", "list", "--porcelain", "-z").split("\0\0"):
        fields = {field.partition(" ")[0]: field.partition(" ")[2]
                  for field in entry.split("\0") if field}
        if fields:
            records.append(fields)
    matching = [row for row in records if Path(row["worktree"]).resolve() == target]
    if any(row.get("branch") == ref and row not in matching for row in records):
        raise ValueError("branch registered at another worktree")
    if matching:
        if (len(matching) != 1 or matching[0].get("branch") != ref
                or any(key in matching[0] for key in ("locked", "bare", "detached"))):
            raise ValueError("worktree registration mismatch or locked")
        if (not target.is_dir() or not (target / ".git").is_file() or (target / ".git").is_symlink()
                or not samefile(git(target, "rev-parse", "--show-toplevel"), target)
                or git(target, "symbolic-ref", "HEAD") != ref):
            raise ValueError("worktree identity mismatch")
        common = (repo / git(repo, "rev-parse", "--git-common-dir")).resolve()
        if not samefile(target / git(target, "rev-parse", "--git-common-dir"), common):
            raise ValueError("worktree repository mismatch")
    elif action == "start":
        if target.exists():
            raise ValueError("unregistered target already exists")
        code, out, err = git_try(repo, "show-ref", "--verify", "--quiet", ref)
        if code == 0:
            git(repo, "worktree", "add", str(target), branch)
        elif code == 1:
            git(repo, "worktree", "add", "-b", branch, str(target), "origin/main")
        else:
            raise RuntimeError(err.strip() or out.strip() or "branch lookup failed")
        return
    else:
        raise ValueError("cleanup requires the registered worktree")
    if action == "start":
        return
    if action not in {"merged", "abandon"}:
        raise ValueError("unknown worktree action")
    if action == "merged":
        if not merge_commit or not re.fullmatch(r"[a-fA-F0-9]{40}|[a-fA-F0-9]{64}", merge_commit):
            raise ValueError("cleanup requires a full local merge commit SHA")
        git(repo, "rev-parse", "--verify", f"{merge_commit}^{{commit}}")
        git(repo, "merge-base", "--is-ancestor", merge_commit, "refs/remotes/origin/main")
        git(repo, "merge-base", "--is-ancestor", ref, merge_commit)
    if git(target, "status", "--porcelain", "--untracked-files=all", "--ignored=matching"):
        raise ValueError("cleanup refused: worktree contains unsaved files")
    git(repo, "worktree", "remove", str(target))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="zi-pi.sh")
    parser.add_argument("action", choices=("start", "merged", "abandon"))
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--worktree", type=Path, required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--merge-commit")
    raw = list(sys.argv[1:] if argv is None else argv)
    separator = raw.index("--") if "--" in raw else len(raw)
    args = parser.parse_args(raw[:separator])
    arguments = raw[separator + 1:]
    try:
        worktree(args.repo, args.worktree, args.branch, args.action, args.merge_commit)
        if args.action == "start":
            os.chdir(args.worktree)
            os.execvp("pi", ["pi", *arguments])
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
