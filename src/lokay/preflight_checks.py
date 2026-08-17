"""Independently invokable preflight findings. Thin runner lives in preflight._check."""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any, Callable


Finding = dict[str, Any]
Check = Callable[..., Finding]

_TRANSIENT_MARKERS = (
    "HTTP 429",
    "HTTP 500",
    "HTTP 502",
    "HTTP 503",
    "HTTP 504",
    "No server is currently available",
    "502 Bad Gateway",
    "503 Service Unavailable",
    "504 Gateway Timeout",
)


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


def _gh_run(argv: list[str], *, timeout: int = 10) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _is_transient_github(stderr: str) -> bool:
    blob = stderr or ""
    return any(marker in blob for marker in _TRANSIENT_MARKERS)


def _local_auth_present() -> bool:
    """Token on disk is not the same question as /user being 503."""
    try:
        return _gh_run(["gh", "auth", "status", "--hostname", "github.com"]).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def check_github_authentication() -> Finding:
    """Prove credentials exist. A 503 on /user is not a missing token.

    Mini froze closeout of a MERGEABLE PR for 15+ ticks because GitHub
    503'd ``gh api user`` while ``gh auth status`` and ``rate_limit`` worked.
    """
    if not shutil.which("gh"):
        return finding("github_authentication", False, "unavailable")
    try:
        probed = _gh_run(["gh", "api", "user", "--silent"])
    except (OSError, subprocess.TimeoutExpired):
        ok = _local_auth_present()
        return finding("github_authentication", ok, "ok" if ok else "unavailable")
    if probed.returncode == 0:
        return finding("github_authentication", True, "ok")
    if _is_transient_github(probed.stderr or "") and _local_auth_present():
        return finding("github_authentication", True, "ok")
    return finding("github_authentication", False, "unavailable")


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
