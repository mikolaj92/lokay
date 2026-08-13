"""Independently invokable preflight findings. Thin runner lives in preflight._check."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable


Finding = dict[str, Any]
Check = Callable[..., Finding]


def finding(name: str, passed: bool, code: str, *, repaired: bool = False) -> Finding:
    return {"name": name, "ok": passed, "code": code[:80], "detail": code[:80], "repaired": repaired}


def check_required_environment(*, repaired: set[str]) -> Finding:
    required = ("PATH", "HOME", "USER", "TMPDIR", "LANG")
    missing = [name for name in required if not os.environ.get(name, "").strip()]
    return finding(
        "required_environment",
        not missing,
        "ok" if not missing else "missing_required",
        repaired="locale" in repaired,
    )


def check_config(*, cfg: Any) -> Finding:
    errors = cfg.validate()
    return finding("config", not errors, "ok" if not errors else "invalid")


def check_repository_catalog_clones(*, cfg: Any) -> Finding:
    clones = [repo for repo in cfg.active_repos() if not repo.clone_path.is_dir()]
    return finding(
        "repository_catalog_clones",
        True,
        "ok" if not clones else "missing_clones_allowed",
    )


def check_github_authentication() -> Finding:
    gh_ok = False
    if shutil.which("gh"):
        try:
            gh_ok = (
                subprocess.run(
                    ["gh", "api", "user", "--silent"],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=10,
                    check=False,
                ).returncode
                == 0
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
    return finding("github_authentication", gh_ok, "ok" if gh_ok else "unavailable")


def check_executor_availability(*, cfg: Any, repaired: set[str]) -> Finding:
    executor_ok = not (cfg.live and cfg.executor_enabled) or shutil.which(cfg.agent_command) is not None
    return finding(
        "executor_availability",
        executor_ok,
        "ok" if executor_ok else "unavailable",
        repaired="executor_path" in repaired,
    )


FINDING_CHECKS: dict[str, Check] = {
    "required_environment": check_required_environment,
    "config": check_config,
    "repository_catalog_clones": check_repository_catalog_clones,
    "github_authentication": check_github_authentication,
    "executor_availability": check_executor_availability,
}
