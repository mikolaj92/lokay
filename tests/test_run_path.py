from __future__ import annotations

import json

import pytest

from lokay.proc import run_path


def _payload(capsys: pytest.CaptureFixture[str]) -> dict:
    return json.loads(capsys.readouterr().out)


@pytest.mark.parametrize("repo", ["mikolaj92/Temida", "mikolaj92/takt"])
def test_product_repo_is_skipped_without_running_path(
    repo: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def unexpected_run_path(**_kwargs):
        pytest.fail("run_path must not run for a product repository")

    monkeypatch.setattr(run_path, "run_path", unexpected_run_path)

    assert run_path.main(["--repo", repo, "--issue", "536", "--live"]) == 0
    assert _payload(capsys) == {
        "ok": True,
        "skipped": True,
        "reason": "repo_not_delivered_by_mini_mill",
        "repo": repo,
    }


def test_mini_mill_repo_runs_path_as_before(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls = []

    def fake_run_path(**kwargs):
        calls.append(kwargs)
        return {"ok": True, "path": kwargs["path_id"]}

    monkeypatch.setattr(run_path, "run_path", fake_run_path)

    assert (
        run_path.main(
            ["--repo", run_path.MINI_MILL_REPO, "--issue", "536", "--live"]
        )
        == 0
    )
    assert len(calls) == 1
    assert calls[0]["repo"] == run_path.MINI_MILL_REPO
    assert calls[0]["issue"] == 536
    assert calls[0]["live"] is True
    assert _payload(capsys) == {"ok": True, "path": "issue_to_pr"}


def test_describe_without_repo_still_describes_package(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        run_path, "describe_package", lambda package: {"package": package or "default"}
    )

    assert run_path.main(["--describe"]) == 0
    assert _payload(capsys) == {"ok": True, "package": "default"}
