"""gh survey budget: 429 detection, backoff, runner retries, pacing."""

from __future__ import annotations

from lokay.gh_rate import backoff_seconds, is_rate_limit_text, survey_pace
from lokay.runner import CommandSpec, Runner


def test_is_rate_limit_text_detects_common_shapes():
    assert is_rate_limit_text("HTTP 429: rate limit exceeded")
    assert is_rate_limit_text("secondary rate limit")
    assert is_rate_limit_text("", "API rate limit exceeded for user")
    assert not is_rate_limit_text("not found")
    assert not is_rate_limit_text("")


def test_backoff_seconds_grows_and_caps():
    assert backoff_seconds(0) == 1
    assert backoff_seconds(1) == 2
    assert backoff_seconds(5) == 32
    assert backoff_seconds(10) == 32


def test_survey_pace_honors_config_ms():
    slept: list[float] = []

    class Cfg:
        gh_survey_pace_ms = 250

    survey_pace(Cfg(), sleep_fn=slept.append)
    assert slept == [0.25]


def test_survey_pace_skips_when_disabled():
    slept: list[float] = []

    class Cfg:
        gh_survey_pace_ms = 0

    survey_pace(Cfg(), sleep_fn=slept.append)
    assert slept == []


def test_runner_retries_gh_429_then_succeeds(monkeypatch):
    calls = {"n": 0}
    sleeps: list[float] = []

    def fake_run(*args, **kwargs):
        calls["n"] += 1

        class R:
            if calls["n"] < 3:
                returncode = 1
                stdout = ""
                stderr = "HTTP 429: API rate limit exceeded"
            else:
                returncode = 0
                stdout = "[]"
                stderr = ""

        return R()

    monkeypatch.setattr("lokay.runner.subprocess.run", fake_run)
    result = Runner(gh_retry_max=3, sleep_fn=sleeps.append).run(
        CommandSpec(argv=("gh", "pr", "list", "--repo", "a/b")),
        live=True,
    )
    assert result.returncode == 0
    assert calls["n"] == 3
    assert sleeps == [1.0, 2.0]


def test_runner_exhausts_429_and_run_checked_raises(monkeypatch):
    sleeps: list[float] = []

    def fake_run(*args, **kwargs):
        class R:
            returncode = 1
            stdout = ""
            stderr = "secondary rate limit triggered"

        return R()

    monkeypatch.setattr("lokay.runner.subprocess.run", fake_run)
    runner = Runner(gh_retry_max=2, sleep_fn=sleeps.append)
    result = runner.run(CommandSpec(argv=("gh", "issue", "list")), live=True)
    assert result.returncode == 1
    assert len(sleeps) == 2
    try:
        runner.run_checked(CommandSpec(argv=("gh", "issue", "list")), live=True)
        raise AssertionError("expected rate-limit RuntimeError")
    except RuntimeError as exc:
        assert "rate limit exhausted" in str(exc)


def test_runner_does_not_retry_non_rate_errors(monkeypatch):
    calls = {"n": 0}

    def fake_run(*args, **kwargs):
        calls["n"] += 1

        class R:
            returncode = 1
            stdout = ""
            stderr = "Not Found"

        return R()

    monkeypatch.setattr("lokay.runner.subprocess.run", fake_run)
    result = Runner(gh_retry_max=5, sleep_fn=lambda *_: None).run(
        CommandSpec(argv=("gh", "api", "user")),
        live=True,
    )
    assert result.returncode == 1
    assert calls["n"] == 1
