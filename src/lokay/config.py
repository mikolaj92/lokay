from __future__ import annotations

import math
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
STATE = Path.home() / ".lokay"


def tick_budget(env: dict[str, str] | None = None) -> float:
    value = (os.environ if env is None else env).get("LOKAY_TICK_BUDGET", "2700")
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        raise ValueError("LOKAY_TICK_BUDGET must be finite positive seconds") from None
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("LOKAY_TICK_BUDGET must be finite positive seconds")
    return seconds


def load_repos(path: Path | None = None) -> list[dict]:
    if path is None:
        path = Path(os.environ.get("LOKAY2_REPOS_FILE") or ROOT / "repos.yaml")
    raw = yaml.safe_load(path.read_text()) or {}
    repos = raw.get("repos") or []
    for repo in repos:
        keys = set(repo)
        if keys - {"setup"} != {"name", "clone_path", "test", "merge"}:
            raise ValueError(f"repo keys must be name, clone_path, test, merge, optional setup: {repo.get('name')}")
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
    return repos
