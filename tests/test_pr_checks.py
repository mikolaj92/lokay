"""PR checks classification: no-checks is not a failure."""

import json

import pytest

from lokay.code import github as github_code
from lokay.gh_prs import pr_checks_report
from lokay.proc import pr_checks
from lokay.proc.pr_route import run_pr_route
from lokay.runner import CommandResult, CommandSpec




def test_factory_repo_still_checks(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = type("Cfg", (), {"require_checks": True})()
    sentinel_runner = object()
    calls: list[tuple[object, str, int, bool]] = []

    monkeypatch.setattr(pr_checks, "load_cfg", lambda _args: cfg)
    monkeypatch.setattr(pr_checks, "runner", lambda: sentinel_runner)

    def report(
        check_runner: object, repo: str, pr: int, *, live: bool
    ) -> dict[str, object]:
        calls.append((check_runner, repo, pr, live))
        return {"status": "passed", "no_checks": False, "text": "all good"}

    monkeypatch.setattr(github_code, "pr_checks_report", report)

    assert pr_checks.main(["--repo", "mikolaj92/lokay", "--pr", "488"]) == 0
    assert calls == [(sentinel_runner, "mikolaj92/lokay", 488, True)]
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "passed"
    assert payload["green"] is True
    assert payload["merge_ok"] is True
    assert payload["require_checks"] is True


class _FakeRunner:
    def __init__(
        self,
        returncode: int,
        stdout: str = "",
        stderr: str = "",
        *,
        timed_out: bool = False,
    ):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.timed_out = timed_out

    def run(self, spec: CommandSpec, *, live: bool) -> CommandResult:
        return CommandResult(
            spec=spec,
            executed=live,
            returncode=self.returncode if live else 0,
            stdout=self.stdout if live else "",
            stderr=self.stderr if live else "",
            timed_out=self.timed_out if live else False,
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


def test_transient_github_503_is_pending_and_not_green():
    r = _FakeRunner(
        1,
        stderr="HTTP 503: No server is currently available to service your request",
    )
    rep = pr_checks_report(r, "a/b", 1, live=True)  # type: ignore[arg-type]
    assert rep["status"] == "pending"
    assert rep["green"] is False
    assert rep["no_checks"] is False


def test_transient_github_429_is_pending_and_not_green():
    r = _FakeRunner(1, stderr="HTTP 429: API rate limit exceeded")
    rep = pr_checks_report(r, "a/b", 1, live=True)  # type: ignore[arg-type]
    assert rep["status"] == "pending"
    assert rep["green"] is False


def test_timed_out_check_read_is_pending_not_failed_ci():
    r = _FakeRunner(
        124,
        stderr="timed out after 120 seconds",
        timed_out=True,
    )

    rep = pr_checks_report(r, "a/b", 1, live=True)  # type: ignore[arg-type]

    assert rep["status"] == "pending"
    assert rep["green"] is False
    assert rep["no_checks"] is False
    routed = run_pr_route(checks=rep, merge_enabled=True)
    assert routed["route"] == "wait"
    assert routed["reason"] == "checks_pending"
    assert routed["repairable"] is False
