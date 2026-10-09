from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
STATE = Path.home() / ".lokay2"


def load_repos(path: Path | None = None) -> list[dict]:
    raw = yaml.safe_load((path or ROOT / "repos.yaml").read_text()) or {}
    repos = raw.get("repos") or []
    for repo in repos:
        keys = set(repo)
        if keys != {"name", "clone_path", "test", "merge"}:
            raise ValueError(f"repo keys must be name, clone_path, test, merge: {repo.get('name')}")
        if repo["merge"] is True:
            repo["merge"] = "on"
        elif repo["merge"] is False:
            repo["merge"] = "off"
        if repo["merge"] not in ("on", "off"):
            raise ValueError("merge must be on or off")
        if not isinstance(repo["test"], list):
            raise ValueError("test must be a list")
    return repos
