from __future__ import annotations

import argparse
import os
from pathlib import Path

from lokay.config import Config, load_config
from lokay.runner import Runner


def add_config(p: argparse.ArgumentParser) -> None:
    p.add_argument("--config", help="config.yaml path")


def add_config_live(p: argparse.ArgumentParser) -> None:
    """Mutating tools: --live enables writes."""
    add_config(p)
    p.add_argument(
        "--live",
        action="store_true",
        help="allow mutations (git push, gh edit/create/merge, agent execute)",
    )


def add_config_read(p: argparse.ArgumentParser) -> None:
    """Read-only tools: hit network by default; --offline plans empty."""
    add_config(p)
    p.add_argument(
        "--offline",
        action="store_true",
        help="do not call GitHub (return empty/planned)",
    )


def load_cfg(args: argparse.Namespace) -> Config:
    return load_config(getattr(args, "config", None))


def read_live(args: argparse.Namespace) -> bool:
    if getattr(args, "offline", False):
        return False
    if os.environ.get("LOKAY_OFFLINE", "").strip() in {"1", "true", "yes"}:
        return False
    return True


def mutations_allowed(*, live_flag: bool) -> bool:
    return bool(live_flag)


def agent_execute_allowed(cfg: Config, *, live_flag: bool) -> bool:
    return bool(live_flag and cfg.mode == "live" and cfg.executor_enabled)


def runner() -> Runner:
    return Runner()


def resolve_repo_clone(cfg: Config, repo_name: str) -> Path:
    for r in cfg.repos:
        if r.name == repo_name:
            return r.clone_path
    raise KeyError(f"repo not in config: {repo_name}")
