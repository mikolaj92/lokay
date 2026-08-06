"""PR checks classification: no-checks is not a failure."""

from lokay.gh_prs import pr_checks_report
from lokay.runner import CommandResult, CommandSpec


class _FakeRunner:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

    def run(self, spec: CommandSpec, *, live: bool) -> CommandResult:
        return CommandResult(
            spec=spec,
            executed=live,
            returncode=self.returncode if live else 0,
            stdout=self.stdout if live else "",
            stderr=self.stderr if live else "",
        )


def test_no_checks_reported():
    r = _FakeRunner(1, stderr="no checks reported on the 'ai/fix/x' branch\n")
    rep = pr_checks_report(r, "a/b", 1, live=True)  # type: ignore[arg-type]
    assert rep["status"] == "none"
    assert rep["no_checks"] is True
    assert rep["green"] is False


def test_passed():
    r = _FakeRunner(0, stdout="all good\n")
    rep = pr_checks_report(r, "a/b", 1, live=True)  # type: ignore[arg-type]
    assert rep["status"] == "passed"
    assert rep["green"] is True


def test_pending_exit_8():
    r = _FakeRunner(8, stdout="check pending\n")
    rep = pr_checks_report(r, "a/b", 1, live=True)  # type: ignore[arg-type]
    assert rep["status"] == "pending"


def test_failed():
    r = _FakeRunner(1, stdout="build fail\n")
    rep = pr_checks_report(r, "a/b", 1, live=True)  # type: ignore[arg-type]
    assert rep["status"] == "failed"
    assert rep["green"] is False
