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
    """Read-only tools: hit network by default; --offline plans empty.

    ``--live`` is accepted as a no-op so factory-pass survey atoms can
    forward the mill live flag. Network is already the default; ``--offline``
    still wins in ``read_live``.
    """
    add_config(p)
    p.add_argument(
        "--offline",
        action="store_true",
        help="do not call GitHub (return empty/planned)",
    )
    p.add_argument(
        "--live",
        action="store_true",
        help="accepted for factory-pass compatibility (network is default)",
    )


def load_cfg(args: argparse.Namespace) -> Config:
    return load_config(getattr(args, "config", None))


def read_live(args: argparse.Namespace) -> bool:
    if getattr(args, "offline", False):
        return False
    if os.environ.get("LOKAY_OFFLINE", "").strip() in {"1", "true", "yes"}:
        return False
    return True


def mutations_allowed(*, live_flag: bool, cfg: Config | None = None) -> bool:
    if not live_flag:
        return False
    if cfg is None:
        raise RuntimeError("live mutation requires config for the health gate")
    from lokay.preflight import require_healthy

    require_healthy(str(cfg.config_path) if cfg.config_path else None)
    return True


def agent_execute_allowed(cfg: Config, *, live_flag: bool) -> bool:
    """Allow a mutating/coding agent only after the live health gate."""
    if live_flag:
        from lokay.preflight import require_healthy

        require_healthy(str(cfg.config_path) if cfg.config_path else None)
    return bool(live_flag and cfg.mode == "live" and cfg.executor_enabled)


def semantic_agent_allowed(cfg: Config, *, live_flag: bool) -> bool:
    """Enable a read-only semantic call without minting/owning the mill lease.

    Intake, queue-conflict, and localization agents only return structured
    advice. Their deterministic callers retain all mutation and health gates;
    requiring the singleton lease here would make a nested semantic call own
    orchestration policy and would also reject hermetic in-process passes.
    """
    return bool(live_flag and cfg.mode == "live" and cfg.executor_enabled)


def runner(cfg: Config | None = None) -> Runner:
    retry = int(getattr(cfg, "gh_retry_max", 3) or 3) if cfg is not None else 3
    return Runner(gh_retry_max=retry)


def resolve_repo_clone(cfg: Config, repo_name: str) -> Path:
    for r in cfg.repos:
        if r.name == repo_name:
            return r.clone_path
    raise KeyError(f"repo not in config: {repo_name}")
