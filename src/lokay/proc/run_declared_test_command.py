"""Run one declared local test command in a deliberately small environment."""

from __future__ import annotations

import os

from lokay.proc._common import runner
from lokay.runner import CommandSpec
from lokay.proc.test_local import TEST_TIMEOUT_SECONDS

# These values locate ordinary user tools and temporary files. Fala protocol
# variables, credentials, harness state, and application-specific state are not
# inherited by repository test commands; Fala atom communication stays in its
# manifest/result envelope.
_TEST_ENV = ("PATH", "HOME", "USER", "TMPDIR", "LANG", "LC_ALL", "TZ")


def _test_environment() -> dict[str, str]:
    env = {key: os.environ[key] for key in _TEST_ENV if key in os.environ}
    env.update({"LOKAY_HEALTH_LEASE": "", "LOKAY_HEALTH_LEASE_PATH": ""})
    return env


def run(inspected: dict, argv: list[str]) -> dict:
    try:
        result = runner().run(
            CommandSpec(
                tuple(argv),
                cwd=inspected["worktree"],
                env=_test_environment(),
                timeout_seconds=TEST_TIMEOUT_SECONDS,
                inherit_env=False,
            ),
            live=True,
        )
    except Exception as exc:
        return {"ok": True, "route": "error", "error": str(exc)}
    return {
        "ok": True,
        "route": "green" if result.returncode == 0 else "red",
        "returncode": result.returncode,
        "tests": " ".join(argv),
        "stdout_tail": (result.stdout or "")[-4000:],
        "stderr_tail": (result.stderr or "")[-2000:],
    }
