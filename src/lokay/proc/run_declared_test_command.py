"""Run exactly one declared local test command with the mill lease stripped."""

from lokay.proc._common import runner
from lokay.runner import CommandSpec
from lokay.proc.test_local import TEST_TIMEOUT_SECONDS


def run(inspected: dict, argv: list[str]) -> dict:
    try:
        result = runner().run(
            CommandSpec(
                tuple(argv),
                cwd=inspected["worktree"],
                env={"LOKAY_HEALTH_LEASE": "", "LOKAY_HEALTH_LEASE_PATH": ""},
                timeout_seconds=TEST_TIMEOUT_SECONDS,
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
