"""Run the complete local suite with an isolated HOME for one candidate."""

import tempfile
from lokay.proc._common import runner
from lokay.runner import CommandSpec


def run_tests(identity: dict) -> dict:
    with tempfile.TemporaryDirectory(prefix="lokay-self-repair-pytest-") as home:
        out = runner().run(
            CommandSpec(
                ("uv", "run", "--extra", "dev", "pytest", "-q"),
                cwd=identity["worktree"],
                env={"HOME": home, "PYTEST_ADDOPTS": "-p no:cacheprovider"},
                timeout_seconds=1800,
            ),
            live=True,
        )
    return {
        **identity,
        "ok": out.returncode == 0,
        "route": "untracked" if out.returncode == 0 else "failed",
        "error": "" if out.returncode == 0 else "self-repair validation suite failed",
    }
