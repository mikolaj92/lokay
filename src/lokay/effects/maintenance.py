from __future__ import annotations

import json
import math
import os
import re
import shutil
import time
from contextvars import ContextVar
from pathlib import Path

from lokay import store
from lokay.config import HOME, load_repos
from lokay.effects.git import git_try
from lokay.effects.pi import run_process
from lokay.effects.tests import UV_CACHE_DIR


ENV: ContextVar[dict[str, str] | None] = ContextVar("maintenance_env", default=None)


def sweep(aggressive: bool) -> None:
    home = Path.home()
    directory = HOME
    timestamp = directory / "sweep.json"
    errors = []
    worktrees = branches = 0
    cache_prune: dict[str, str | int] = {"result": "skipped"}
    lokay_cache_prune: dict[str, str | int] = {"result": "skipped"}
    before = None
    attempted = False
    env = ENV.get()
    child = {**(os.environ if env is None else env),
             "GIT_NO_LAZY_FETCH": "1", "GIT_TERMINAL_PROMPT": "0"}

    def checked(path, args):
        code, out, err = git_try(path, *args, env=child)
        if code:
            raise RuntimeError(f"{path}: {' '.join(args)}: {err.strip() or out.strip() or code}")
        return out

    def origin(path):
        url = checked(path, ["remote", "get-url", "origin"]).strip()
        match = re.fullmatch(
            r"(?:https?://(?:[^/@]+@)?github\.com/|ssh://(?:[^/@]+@)?github\.com/|(?:[^/@:]+@)?github\.com:)([^/\s]+/[^/\s]+?)(?:\.git)?/?",
            url, re.IGNORECASE,
        )
        return match[1].casefold() if match else None

    def registrations(path):
        records = []
        record = {}
        for field in checked(path, ["worktree", "list", "--porcelain", "-z"]).split("\0"):
            if not field:
                if record:
                    records.append(record)
                    record = {}
            else:
                key, _, value = field.partition(" ")
                if key in record:
                    raise ValueError(f"{path}: duplicate worktree field")
                record[key] = value
        if record:
            records.append(record)
        if not records or any(not row.get("worktree") for row in records):
            raise ValueError(f"{path}: invalid worktree registrations")
        return records

    try:
        with store.shared_file_lock(directory / "sweep.lock"):
            try:
                now = time.time()
                if not aggressive and timestamp.exists():
                    last = json.loads(timestamp.read_text())["time"]
                    if not isinstance(last, (int, float)) or not math.isfinite(last):
                        raise ValueError("invalid sweep timestamp")
                    if now - last < 3600:
                        return
                attempted = True
                before = shutil.disk_usage(home).free
                store.write_json(timestamp, {"time": now})
                repos_file = child.get("LOKAY2_REPOS_FILE")
                configured = load_repos(Path(repos_file) if repos_file else None)
                owners = {(str(Path(repo["clone_path"]).expanduser()), repo["name"].casefold())
                          for repo in configured}
                owners.add((str(directory / "host"), "mikolaj92/lokay"))
                candidates = sorted((*directory.glob("host-wt-*"), *directory.glob("factory-pass-*")))
                cwd = Path.cwd().resolve()
                seen = set()
                for raw, name in sorted(owners):
                    try:
                        owner = Path(raw)
                        if name == "mikolaj92/temida" or owner.is_symlink() or not owner.is_dir():
                            continue
                        owner = owner.resolve()
                        if owner in seen:
                            continue
                        if origin(owner) != name:
                            continue
                        if Path(checked(owner, ["rev-parse", "--show-toplevel"]).strip()).resolve() != owner:
                            continue
                        common = (owner / checked(owner, ["rev-parse", "--git-common-dir"]).strip()).resolve()
                        git_dir = (owner / checked(owner, ["rev-parse", "--git-dir"]).strip()).resolve()
                        if common != git_dir or not (owner / ".git").is_dir():
                            continue
                        seen.add(owner)
                        records = registrations(owner)
                        for path in candidates:
                            try:
                                if path.is_symlink() or not path.is_dir():
                                    continue
                                dotgit = path / ".git"
                                if dotgit.is_symlink() or not dotgit.is_file():
                                    continue
                                resolved = path.resolve()
                                if resolved == owner or cwd == resolved or resolved in cwd.parents:
                                    continue
                                matches = [row for row in records if row["worktree"] == str(path)]
                                if len(matches) != 1 or matches[0] is records[0] or "locked" in matches[0]:
                                    continue
                                if not aggressive and now - path.stat().st_mtime < 86400:
                                    continue
                                if (path / checked(path, ["rev-parse", "--git-common-dir"]).strip()).resolve() != common:
                                    continue
                                if Path(checked(path, ["rev-parse", "--show-toplevel"]).strip()).resolve() != resolved:
                                    continue
                                if origin(path) != name:
                                    continue
                                if checked(path, ["status", "--porcelain", "--untracked-files=all"]).strip():
                                    continue
                                if not checked(path, ["for-each-ref", "--contains=HEAD", "--format=%(refname)",
                                                      "refs/remotes/origin/"]).strip():
                                    continue
                                checked(owner, ["worktree", "remove", str(path)])
                                worktrees += 1
                                checked(owner, ["worktree", "prune"])
                            except Exception as exc:
                                errors.append(f"{path}: {exc}")
                        if checked(owner, ["status", "--porcelain", "--untracked-files=all"]).strip():
                            continue
                        if not checked(owner, ["for-each-ref", "--contains=HEAD", "--format=%(refname)",
                                               "refs/remotes/origin/"]).strip():
                            continue
                        base = checked(owner, ["symbolic-ref", "refs/remotes/origin/HEAD"]).strip()
                        if not base.startswith("refs/remotes/origin/") or base == "refs/remotes/origin/HEAD":
                            continue
                        checked(owner, ["rev-parse", "--verify", f"{base}^{{commit}}"])
                        merged = checked(owner, ["for-each-ref", f"--merged={base}", "--format=%(refname)",
                                                 "refs/heads/lokay/"])
                        for ref in sorted(merged.splitlines()):
                            try:
                                if not ref.startswith("refs/heads/lokay/"):
                                    continue
                                records = registrations(owner)
                                if any(row.get("branch") == ref for row in records):
                                    continue
                                checked(owner, ["merge-base", "--is-ancestor", ref, base])
                                checked(owner, ["branch", "-D", "--", ref.removeprefix("refs/heads/")])
                                branches += 1
                            except Exception as exc:
                                errors.append(f"{owner}: {ref}: {exc}")
                    except Exception as exc:
                        errors.append(f"{raw}: {exc}")
                prunes = [("uv cache prune", child, cache_prune)]
                if UV_CACHE_DIR.exists():
                    prunes.append(("lokay uv cache prune",
                                   {**child, "UV_CACHE_DIR": str(UV_CACHE_DIR)}, lokay_cache_prune))
                for label, prune_env, result in prunes:
                    try:
                        proc = run_process(["uv", "cache", "prune"], env=prune_env, timeout=300)
                        result.update(result="ok" if proc.returncode == 0 else "failed",
                                      returncode=proc.returncode)
                        if proc.returncode:
                            errors.append(f"{label}: {proc.stderr or proc.stdout or proc.returncode}")
                    except Exception as exc:
                        result.update(result="failed")
                        errors.append(f"{label}: {exc}")
            except Exception as exc:
                attempted = True
                errors.append(str(exc))
            finally:
                if attempted:
                    freed = 0
                    try:
                        if before is not None:
                            freed = max(0, shutil.disk_usage(home).free - before)
                    except Exception as exc:
                        errors.append(str(exc))
                    store.log_event("sweep", freed_bytes=freed, worktrees=worktrees, branches=branches,
                                    cache_prune=cache_prune, lokay_cache_prune=lokay_cache_prune, errors=errors)
    except Exception as exc:
        if not attempted:
            store.log_event("sweep", freed_bytes=0, worktrees=0, branches=0,
                            cache_prune=cache_prune, lokay_cache_prune=lokay_cache_prune, errors=[str(exc)])
