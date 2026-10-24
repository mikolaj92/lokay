from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from lokay import store
from lokay.effects.git import BASE_BRANCHES, ensure_worktree, git, git_try, worktree_remove
from lokay.effects.pi import pi_env, run_pi


def main(argv=None):
    parser = argparse.ArgumentParser(prog="zi-pi.sh")
    parser.add_argument("repo", type=Path)
    parser.add_argument("issue", type=int)
    parser.add_argument("action", choices=("run", "merged", "abandon"))
    parser.add_argument("prompt", nargs="?")
    args = parser.parse_args(argv)
    if args.issue <= 0:
        parser.error("issue must be positive")
    if args.action == "run" and not args.prompt:
        parser.error("run requires a prompt")
    if args.action != "run" and args.prompt is not None:
        parser.error("cleanup does not accept a prompt")
    repo = args.repo.resolve()
    branch = f"lokay/{args.issue}"
    worktree = repo.parent / f"{repo.name}-wt-{args.issue}"
    if Path(git(repo, "rev-parse", "--show-toplevel")).resolve() != repo:
        raise ValueError("repository top-level mismatch")
    common = (repo / git(repo, "rev-parse", "--git-common-dir")).resolve()
    with store.shared_file_lock(common / f"zi-pi-{args.issue}.lock"):
        BASE_BRANCHES[(repo, None)] = "main"
        if args.action == "run":
            code, out, err = git_try(repo, "show-ref", "--verify", "--quiet", f"refs/heads/{branch}")
            if code == 1 and not worktree.exists() and not worktree.is_symlink():
                git(repo, "fetch", "origin", "refs/heads/main:refs/remotes/origin/main")
                git(repo, "branch", branch, "refs/remotes/origin/main")
            elif code not in (0, 1):
                raise RuntimeError(err.strip() or out.strip() or "branch lookup failed")
            outcome = ensure_worktree(repo, branch, worktree)
            if outcome["result"] != "added":
                raise RuntimeError(outcome.get("error") or "worktree setup failed")
            env = pi_env(os.environ, worktree)
            proc = run_pi(worktree, args.prompt, env=env, cwd=worktree, guarded=False)
            print(proc.stdout or "", end="")
            print(proc.stderr or "", end="", file=sys.stderr)
            return proc.returncode
        if args.action == "merged":
            git(repo, "fetch", "origin", "refs/heads/main:refs/remotes/origin/main")
            code, out, err = git_try(repo, "merge-base", "--is-ancestor", f"refs/heads/{branch}",
                                     "refs/remotes/origin/main")
            if code != 0:
                raise RuntimeError(err.strip() or out.strip() or "branch not confirmed on origin/main")
        outcome = worktree_remove(repo, worktree, safe=True, branch=branch,
                                  patch_path=common / f"zi-pi-{args.issue}-cleanup.patch")
        if outcome["result"] != "removed":
            raise RuntimeError(outcome.get("error") or outcome.get("reason") or "cleanup failed")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
