"""Repository boundary for issue-to-PR composition."""

from __future__ import annotations

import pytest

from lokay.compose import issue_to_pr


@pytest.mark.parametrize("repo", ["mikolaj92/Temida", "mikolaj92/takt"])
def test_product_repo_skips_without_activation_config_github_git_fala_or_state(
    repo: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_if_called(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("product repositories must not perform delivery I/O")

    monkeypatch.setattr(issue_to_pr, "_await_detach_activation", fail_if_called)
    monkeypatch.setattr(issue_to_pr, "load_config", fail_if_called)
    monkeypatch.setattr(issue_to_pr, "_delivery_stop_reason", fail_if_called)
    monkeypatch.setattr(issue_to_pr, "run_path", fail_if_called)
    monkeypatch.setattr(issue_to_pr, "append_event", fail_if_called)

    assert issue_to_pr.compose_issue_to_pr(
        config_path=None,
        repo=repo,
        issue_number=530,
        live=True,
    ) == {
        "ok": True,
        "kind": "issue_to_pr",
        "engine": "fala",
        "planned": False,
        "skipped": True,
        "reason": "repo_not_delivered_by_mini_mill",
        "repo": repo,
        "issue": 530,
    }


def test_lokay_repo_still_runs_issue_to_pr_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    def run(**kwargs: object) -> dict[str, object]:
        calls.append(kwargs)
        return {"ok": True}

    monkeypatch.setattr(issue_to_pr, "_await_detach_activation", lambda: True)
    monkeypatch.setattr(issue_to_pr, "run_path", run)
    monkeypatch.setattr(
        issue_to_pr, "load_config", lambda _path: (_ for _ in ()).throw(RuntimeError)
    )

    result = issue_to_pr.compose_issue_to_pr(
        config_path=None,
        repo="mikolaj92/lokay",
        issue_number=530,
        live=False,
    )

    assert calls == [{
        "path_id": "issue_to_pr",
        "repo": "mikolaj92/lokay",
        "issue": 530,
        "config_path": None,
        "live": False,
        "package_path": None,
        "extra_inputs": {"incident_fingerprint": "", "keep_issue_open": False},
    }]
    assert result == {
        "ok": True,
        "kind": "issue_to_pr",
        "engine": "fala",
        "planned": True,
    }
