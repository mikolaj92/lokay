from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from lokay.proc import get_issue


@pytest.mark.parametrize("repo", ["mikolaj92/Temida", "mikolaj92/takt"])
def test_get_issue_skips_product_repo_without_gh(
    repo: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(get_issue, "load_cfg", lambda _args: object())
    monkeypatch.setattr(get_issue, "read_live", lambda _args: True)

    def fail_if_called(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("product repositories must not call GitHub")

    monkeypatch.setattr(get_issue, "runner", fail_if_called)
    monkeypatch.setattr(get_issue, "get_issue", fail_if_called)

    assert get_issue.main(["--repo", repo, "--issue", "459", "--live"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "ok": True,
        "offline": False,
        "repo": repo,
        "issue": None,
    }


def test_get_issue_still_fetches_lokay(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = object()
    issue = SimpleNamespace(to_dict=lambda: {"number": 459, "state": "OPEN"})
    sentinel_runner = object()
    seen: list[tuple[object, object, str, int, bool]] = []

    monkeypatch.setattr(get_issue, "load_cfg", lambda _args: cfg)
    monkeypatch.setattr(get_issue, "read_live", lambda _args: True)
    monkeypatch.setattr(get_issue, "runner", lambda: sentinel_runner)

    def fake_get_issue(
        issue_runner: object,
        loaded_cfg: object,
        repo: str,
        number: int,
        *,
        live: bool,
    ) -> object:
        seen.append((issue_runner, loaded_cfg, repo, number, live))
        return issue

    monkeypatch.setattr(get_issue, "get_issue", fake_get_issue)

    assert (
        get_issue.main(
            ["--repo", "mikolaj92/lokay", "--issue", "459", "--live"]
        )
        == 0
    )
    assert seen == [(sentinel_runner, cfg, "mikolaj92/lokay", 459, True)]
    assert json.loads(capsys.readouterr().out) == {
        "ok": True,
        "offline": False,
        "issue": {"number": 459, "state": "OPEN"},
    }
