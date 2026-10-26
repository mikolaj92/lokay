from __future__ import annotations

import os
import sys
from pathlib import Path
from functools import cache

HOME = Path.home() / ".lokay"
ROOT = Path(__file__).resolve().parents[2]


def load_repos(path: Path | None = None) -> list[dict]:
    if path is None:
        path = Path(os.environ.get("LOKAY2_REPOS_FILE") or ROOT / "repos.yaml")
    return _load_repos(path.resolve())


@cache
def _load_repos(path: Path) -> list[dict]:
    import yaml

    raw = yaml.safe_load(path.read_text()) or {}
    repos = raw.get("repos") or []
    configured = []
    for repo in repos:
        keys = set(repo)
        if keys - {"setup", "test_timeout", "syntax_only"} != {"name", "clone_path", "test", "merge"}:
            raise ValueError(f"repo keys must be name, clone_path, test, merge, optional setup, test_timeout, syntax_only: {repo.get('name')}")
        if "syntax_only" in repo and type(repo["syntax_only"]) is not bool:
            raise ValueError("syntax_only must be a bool")
        if "test_timeout" in repo and (type(repo["test_timeout"]) is not int or repo["test_timeout"] <= 0):
            raise ValueError("test_timeout must be positive integer seconds")
        if "setup" in repo and (not isinstance(repo["setup"], list) or
                                any(not isinstance(arg, str) for arg in repo["setup"])):
            raise ValueError("setup must be a list of argv strings")
        if repo["merge"] is True:
            repo["merge"] = "on"
        elif repo["merge"] is False:
            repo["merge"] = "off"
        if repo["merge"] not in ("on", "off"):
            raise ValueError("merge must be on or off")
        if not isinstance(repo["test"], list):
            raise ValueError("test must be a list")
        clone = Path(repo["clone_path"]).expanduser()
        runners = ("pytest", "unittest", "swift test", "npm test", "make test", "bats",
                   "pixi run", "scripts/check.sh", "scripts/test.sh")
        if (repo["merge"] == "on" and not repo.get("syntax_only", False)
                and any((clone / name).is_dir() for name in ("tests", "Tests"))
                and not any(runner in " ".join(repo["test"]) for runner in runners)):
            print(f"config: {repo['name']} has tests but test command does not run them", file=sys.stderr)
        if not repo["test"]:
            from lokay.store import log_event

            log_event("config", repo=repo["name"], reason="repo has no checks configured")
            continue
        configured.append(repo)
    return configured


def repo(name: str) -> dict:
    return next(row for row in load_repos() if row["name"] == name)
