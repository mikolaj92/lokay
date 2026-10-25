from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from lokay.effects.gh import _gh
from lokay.effects.git import git, git_try, samefile, worktree_record_matches
from lokay.effects.pi import run_process


def verify(repo: Path, worktree: Path, branch: str) -> None:
    if (worktree.is_symlink() or not worktree.is_dir()
            or not (worktree / ".git").is_file() or (worktree / ".git").is_symlink()):
        raise ValueError("expected a linked worktree, not a symlink")
    common = (repo / git(repo, "rev-parse", "--git-common-dir")).resolve()
    records = git(repo, "worktree", "list", "--porcelain", "-z").split("\0\0")
    matches = [record.split("\0") for record in records if worktree_record_matches(record, worktree)]
    if (len(matches) != 1 or f"branch refs/heads/{branch}" not in matches[0]
            or any(field.startswith("locked") for field in matches[0])
            or samefile(repo, worktree)
            or not samefile(git(worktree, "rev-parse", "--show-toplevel"), worktree)
            or not samefile(worktree / git(worktree, "rev-parse", "--git-common-dir"), common)
            or git(worktree, "symbolic-ref", "HEAD") != f"refs/heads/{branch}"):
        raise ValueError("worktree repository, registration or branch mismatch, or locked")


def prepare(repo: Path, worktree: Path, branch: str) -> None:
    if worktree.exists() or worktree.is_symlink():
        verify(repo, worktree, branch)
        return
    records = git(repo, "worktree", "list", "--porcelain", "-z").split("\0\0")
    if any(f"worktree {worktree}" in record.split("\0") for record in records):
        raise ValueError("missing registered worktree; recover it explicitly")
    code, out, err = git_try(repo, "show-ref", "--verify", "--quiet", f"refs/heads/{branch}")
    if code == 0:
        git(repo, "worktree", "add", str(worktree), branch)
    elif code == 1:
        git(repo, "worktree", "add", "-b", branch, str(worktree), "origin/main")
    else:
        raise RuntimeError(err.strip() or out.strip() or "branch lookup failed")
    verify(repo, worktree, branch)


def merged(repo: Path, worktree: Path, branch: str, issue: int, pr: int) -> None:
    origin = git(repo, "remote", "get-url", "origin")
    match = re.fullmatch(r"(?:https://github\.com/|git@github\.com:)([^/]+/[^/]+?)(?:\.git)?/?", origin)
    if not match:
        raise ValueError("expected a GitHub origin")
    name = match[1]
    code, out, err = _gh([
        "pr", "view", str(pr), "--repo", name, "--json",
        "url,state,mergedAt,headRefName,headRefOid,headRepository,closingIssuesReferences",
    ], cwd=repo)
    if code:
        raise RuntimeError(err.strip() or "merge evidence lookup failed")
    evidence = json.loads(out)
    if (not isinstance(evidence, dict) or not isinstance(evidence.get("headRepository"), dict)
            or not isinstance(evidence.get("closingIssuesReferences"), list)
            or not all(isinstance(row, dict) for row in evidence["closingIssuesReferences"])):
        raise ValueError("malformed merge evidence")
    if (evidence.get("url") != f"https://github.com/{name}/pull/{pr}"
            or evidence.get("state") != "MERGED" or not evidence.get("mergedAt")
            or evidence.get("headRefName") != branch
            or evidence.get("headRefOid") != git(worktree, "rev-parse", "HEAD")
            or (evidence.get("headRepository") or {}).get("url") != f"https://github.com/{name}"
            or not any(row.get("url") == f"https://github.com/{name}/issues/{issue}"
                       for row in evidence.get("closingIssuesReferences", []))):
        raise ValueError("merge evidence does not identify this repository, issue and worktree HEAD")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="zi-pi")
    parser.add_argument("action", choices=("run", "merged", "abandon"))
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--issue", type=int, required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--worktree", type=Path, required=True)
    parser.add_argument("--pr", type=int)
    arguments = list(sys.argv[1:] if argv is None else argv)
    separator = arguments.index("--") if "--" in arguments else len(arguments)
    pi_args = arguments[separator + 1:]
    args = parser.parse_args(arguments[:separator])
    repo = args.repo.resolve()
    worktree = args.worktree.parent.resolve() / args.worktree.name
    try:
        if args.issue <= 0 or (args.pr is not None and args.pr <= 0):
            raise ValueError("expected positive issue and PR numbers")
        if not samefile(git(repo, "rev-parse", "--show-toplevel"), repo):
            raise ValueError("repository top-level mismatch")
        git(repo, "check-ref-format", "--branch", args.branch)
        if args.branch.startswith("-") or args.branch in {"main", "master"}:
            raise ValueError("expected a change branch")
        if worktree.name != f"host-wt-zi-{args.issue}" or samefile(repo, worktree):
            raise ValueError("expected host-wt-zi-<issue> worktree")
        if args.action == "run":
            prepare(repo, worktree, args.branch)
            return run_process(["pi", *pi_args], cwd=worktree, timeout=None).returncode
        if pi_args:
            raise ValueError("pi arguments are only allowed for run")
        verify(repo, worktree, args.branch)
        if args.action == "merged":
            if args.pr is None:
                raise ValueError("merged cleanup requires --pr")
            merged(repo, worktree, args.branch, args.issue, args.pr)
        if git(worktree, "status", "--porcelain", "--untracked-files=all", "--ignored"):
            raise ValueError("worktree has local or ignored changes; preserve them before cleanup")
        git(repo, "worktree", "remove", str(worktree))
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        parser.exit(1, f"zi-pi: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
